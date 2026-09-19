"""
Tests for dispatcher/dispatcher.py: the S3-triggered function that reads the
token_count the API already wrote to DynamoDB and pushes a job onto the
AnalysisQueue for the AI worker.

dispatcher.py had zero test coverage before this file. Written alongside a
real fix: a malformed S3 key (fewer path segments than expected) used to
raise an unguarded IndexError; it's now skipped instead.
"""
import json
import os

import boto3
import pytest


@pytest.fixture
def sqs_queue(monkeypatch):
    """A real (moto-mocked) SQS queue, with SQS_QUEUE_URL pointed at it --
    dispatcher.py reads that env var at call time, not import time, so it's
    fine to set it per-test rather than in conftest's global setup."""
    sqs = boto3.client("sqs", region_name=os.environ["AWS_REGION"])
    queue_url = sqs.create_queue(QueueName="clauseiq-test-analysis-queue")["QueueUrl"]
    monkeypatch.setenv("SQS_QUEUE_URL", queue_url)
    return sqs, queue_url


def _s3_event(key: str) -> dict:
    return {"Records": [{"s3": {"object": {"key": key}}}]}


def test_dispatcher_sends_job_with_token_count(seed_agreement, sqs_queue):
    seed_agreement("user-1", "agmt-1", text="short doc")  # token_count = 2 words

    import dispatcher

    sqs, queue_url = sqs_queue
    dispatcher.handler(_s3_event("documents/user-1/agmt-1/original.txt"), None)

    messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1).get("Messages", [])
    assert len(messages) == 1
    body = json.loads(messages[0]["Body"])
    assert body == {
        "agreementId": "agmt-1",
        "userId": "user-1",
        "s3_key": "documents/user-1/agmt-1/original.txt",
        "token_count": 2,
    }


def test_dispatcher_skips_malformed_key_instead_of_crashing(sqs_queue, dynamo_table):
    """A key that doesn't have at least documents/{userId}/{agreementId}/...
    used to raise an unguarded IndexError. It should be skipped instead."""
    import dispatcher

    sqs, queue_url = sqs_queue
    dispatcher.handler(_s3_event("documents/onlyonesegment.txt"), None)

    messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1).get("Messages", [])
    assert messages == []
