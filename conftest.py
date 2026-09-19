"""
Root pytest conftest.

Several modules under api/ read os.environ[...] at IMPORT time (not inside
functions) -- e.g. api/auth.py reads COGNITO_USER_POOL_ID, api/routers/*.py
read S3_BUCKET_NAME. That means these env vars must exist *before* `main.py`
or anything under routers/utils gets imported anywhere in the test session.
This file is collected by pytest before any test module, so setting them at
module scope here (not inside a fixture) is what makes that safe.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
API_DIR = REPO_ROOT / "api"
WORKER_DIR = REPO_ROOT / "worker"
DISPATCHER_DIR = REPO_ROOT / "dispatcher"
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(WORKER_DIR))
sys.path.insert(0, str(DISPATCHER_DIR))

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("BEDROCK_REGION", "us-east-1")
os.environ.setdefault("DYNAMODB_TABLE_NAME", "clauseiq-test")
os.environ.setdefault("S3_BUCKET_NAME", "clauseiq-test-bucket")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_TESTPOOL1")
os.environ.setdefault("COGNITO_APP_CLIENT_ID", "test-client-id")
os.environ.setdefault(
    "PINECONE_SECRET_ARN",
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:clauseiq-pinecone-test",
)
# Dummy credentials so botocore never attempts to resolve a real credential
# chain (e.g. from ~/.aws/credentials) even before moto's mock is active.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")

import boto3  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jose import jwk, jwt  # noqa: E402
from moto import mock_aws  # noqa: E402


@pytest.fixture(autouse=True)
def aws_sandbox():
    """
    Every test runs inside a fresh moto-mocked AWS account. No test in this
    suite can reach real AWS/Bedrock/Pinecone -- moto intercepts at the
    botocore transport layer, so this covers clients created at import time
    (e.g. api/routers/chat.py's module-level `bedrock` client) just as much
    as clients created inside a function.
    """
    with mock_aws():
        yield


@pytest.fixture
def dynamo_table():
    """DynamoDB table with the exact key schema from template.yaml."""
    table = boto3.resource("dynamodb").create_table(
        TableName=os.environ["DYNAMODB_TABLE_NAME"],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


@pytest.fixture
def s3_bucket():
    s3 = boto3.client("s3", region_name=os.environ["AWS_REGION"])
    s3.create_bucket(Bucket=os.environ["S3_BUCKET_NAME"])
    return s3


@pytest.fixture
def seed_agreement(dynamo_table, s3_bucket):
    """
    Returns a factory that drives the *real* write paths -- api/utils/dynamo.py's
    create_agreement() and worker/dynamo.py's set_agreement_status()/
    write_analysis_results()/write_risks()/etc -- to build an agreement in
    whatever state a test needs (UPLOADED, or fully COMPLETED with analysis
    data). This means the fixture itself exercises production code instead of
    hand-crafting DynamoDB items that might drift from what the real writers
    actually produce.
    """
    import hashlib

    from utils.dynamo import create_agreement as api_create_agreement
    import dynamo as worker_dynamo  # worker/dynamo.py

    def _seed(
        user_id: str,
        agreement_id: str,
        text: str = "This is a sample agreement.",
        completed: bool = False,
        ai_data: dict | None = None,
    ):
        s3_key = f"documents/{user_id}/{agreement_id}/original.txt"
        s3_bucket.put_object(
            Bucket=os.environ["S3_BUCKET_NAME"], Key=s3_key, Body=text.encode("utf-8")
        )
        api_create_agreement(
            user_id=user_id,
            agreement_id=agreement_id,
            title="Test Agreement",
            file_count=1,
            source_filenames=["test.txt"],
            token_count=len(text.split()),
            document_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            s3_key=s3_key,
        )

        if completed:
            data = ai_data or {}
            worker_dynamo.set_agreement_status(agreement_id, user_id, "COMPLETED")
            worker_dynamo.write_analysis_results(agreement_id, user_id, data)
            worker_dynamo.write_risks(agreement_id, data.get("risks", []))
            worker_dynamo.write_ambiguous_clauses(agreement_id, data.get("ambiguous_clauses", []))
            worker_dynamo.write_discovered_clauses(agreement_id, data.get("discovered_clauses", []))
            worker_dynamo.write_normalized_checklist(agreement_id, data.get("normalized_checklist", []))

        return s3_key

    return _seed


@pytest.fixture
def client():
    """
    FastAPI TestClient for the real `app` object in api/main.py. Imported
    lazily inside the fixture (not at module scope) so the env-var setup
    above always runs first even under test collection orders pytest
    doesn't guarantee otherwise.
    """
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# JWT / Cognito auth test doubles
#
# api/auth.py verifies incoming tokens against a JWKS fetched from Cognito's
# public well-known endpoint. We never want a test to make that network call
# (it would make the suite flaky and non-hermetic), so instead we generate
# our own RSA keypair, publish its public half as a fake JWKS by monkeypatching
# auth.get_jwks(), and sign test tokens with the private half. This exercises
# the *real* verification code path in auth.py -- signature check, issuer
# check, audience check, expiry check -- just against a key pair we control.
# ---------------------------------------------------------------------------

TEST_KID = "test-key-1"


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


@pytest.fixture
def mock_jwks(monkeypatch, rsa_keypair):
    """Patches auth.get_jwks() to return our test public key instead of hitting Cognito."""
    import auth as auth_module

    _, public_pem = rsa_keypair
    public_jwk = jwk.construct(public_pem, algorithm="RS256").to_dict()
    public_jwk["kid"] = TEST_KID
    public_jwk["use"] = "sig"
    public_jwk["alg"] = "RS256"

    jwks = [public_jwk]
    monkeypatch.setattr(auth_module, "get_jwks", lambda force_refresh=False: jwks)
    monkeypatch.setattr(auth_module, "_jwks", None)
    return jwks


@pytest.fixture
def make_token(rsa_keypair, mock_jwks):
    """
    Returns a factory for minting Cognito-shaped ID tokens signed with the
    test keypair. Callers override individual claims to produce the invalid
    variants (expired, wrong audience, wrong issuer, etc.).
    """
    private_pem, _ = rsa_keypair
    region = os.environ["AWS_REGION"]
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    client_id = os.environ["COGNITO_APP_CLIENT_ID"]

    import time

    def _make(
        sub="test-user-id",
        email="test@example.com",
        aud=None,
        iss=None,
        token_use="id",
        exp_offset_seconds=3600,
        kid=TEST_KID,
    ):
        now = int(time.time())
        claims = {
            "sub": sub,
            "email": email,
            "aud": aud if aud is not None else client_id,
            "iss": iss if iss is not None else f"https://cognito-idp.{region}.amazonaws.com/{pool_id}",
            "token_use": token_use,
            "iat": now,
            "exp": now + exp_offset_seconds,
        }
        return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})

    return _make


@pytest.fixture
def auth_headers(make_token):
    """Convenience: a valid Authorization header for a default test user."""
    token = make_token()
    return {"Authorization": f"Bearer {token}"}
