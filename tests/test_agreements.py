"""
Tests for api/routers/agreements.py: upload (paste + file), validation,
hash-based dedup, ownership isolation, get/list/delete.
"""
import io

import fitz
import pytest
from docx import Document


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Upload: pasted text
# ---------------------------------------------------------------------------

def test_upload_pasted_text_creates_agreement(client, auth_headers, dynamo_table, s3_bucket):
    resp = client.post(
        "/agreements", data={"text": "This is a confidentiality agreement between two parties."}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "UPLOADED"
    assert body["agreementId"].startswith("agmt-")

    # The extracted text really landed in S3 at the key the API says it used.
    item = dynamo_table.get_item(
        Key={"PK": "USER#test-user-id", "SK": f"AGREEMENT#{body['agreementId']}"}
    )["Item"]
    s3_obj = s3_bucket.get_object(Bucket="clauseiq-test-bucket", Key=item["s3_key"])
    assert s3_obj["Body"].read().decode("utf-8") == "This is a confidentiality agreement between two parties."


def test_upload_empty_pasted_text_rejected(client, auth_headers):
    resp = client.post("/agreements", data={"text": "   "}, headers=auth_headers)
    assert resp.status_code == 400


def test_upload_with_neither_text_nor_files_rejected(client, auth_headers):
    resp = client.post("/agreements", headers=auth_headers)
    assert resp.status_code == 400


def test_upload_with_both_text_and_file_rejected(client, auth_headers):
    resp = client.post(
        "/agreements",
        data={"text": "some text"},
        files={"files": ("doc.docx", _make_docx_bytes(["hi"]), "application/vnd.openxmlformats")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_upload_unauthenticated_rejected(client):
    resp = client.post("/agreements", data={"text": "some text"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Upload: files
# ---------------------------------------------------------------------------

def test_upload_unsupported_file_type_rejected(client, auth_headers):
    resp = client.post(
        "/agreements",
        files={"files": ("notes.txt", b"plain text file", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 415


def test_upload_oversized_file_rejected(client, auth_headers):
    # 50MB+ named as .docx so the size check (which runs before extraction)
    # is what trips, not python-docx failing to parse garbage bytes.
    big = b"x" * (50 * 1024 * 1024 + 10)
    resp = client.post(
        "/agreements",
        files={"files": ("huge.docx", big, "application/vnd.openxmlformats")},
        headers=auth_headers,
    )
    assert resp.status_code == 413


def test_upload_more_than_five_files_rejected(client, auth_headers):
    files = [("files", (f"f{i}.docx", _make_docx_bytes([f"doc {i}"]), "application/vnd.openxmlformats")) for i in range(6)]
    resp = client.post("/agreements", files=files, headers=auth_headers)
    assert resp.status_code == 413


def test_upload_real_docx_extracts_paragraph_text(client, auth_headers, dynamo_table, s3_bucket):
    docx_bytes = _make_docx_bytes(["Clause 1: The parties agree to keep terms confidential."])
    resp = client.post(
        "/agreements",
        files={"files": ("nda.docx", docx_bytes, "application/vnd.openxmlformats")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    agreement_id = resp.json()["agreementId"]

    # Extraction output isn't returned by the upload response, so verify it
    # by reading back the S3 object the endpoint wrote (s3_key comes from
    # the agreement's own metadata, exactly as the real client would learn it).
    s3_key = client.get(f"/agreements/{agreement_id}", headers=auth_headers).json()["s3_key"]
    stored_text = s3_bucket.get_object(Bucket="clauseiq-test-bucket", Key=s3_key)["Body"].read().decode("utf-8")
    assert "Clause 1: The parties agree to keep terms confidential." in stored_text


def test_upload_real_pdf_extracts_text(client, auth_headers, dynamo_table, s3_bucket):
    pdf_bytes = _make_pdf_bytes("Termination clause: 30 days notice required.")
    resp = client.post(
        "/agreements",
        files={"files": ("contract.pdf", pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    agreement_id = resp.json()["agreementId"]

    s3_key = client.get(f"/agreements/{agreement_id}", headers=auth_headers).json()["s3_key"]
    stored_text = s3_bucket.get_object(Bucket="clauseiq-test-bucket", Key=s3_key)["Body"].read().decode("utf-8")
    assert "Termination clause" in stored_text


# ---------------------------------------------------------------------------
# Dedup: real re-upload of the identical text
# ---------------------------------------------------------------------------

def test_duplicate_upload_reuses_completed_analysis(client, auth_headers, seed_agreement, dynamo_table):
    text = "This exact agreement text has been analyzed before."
    ai_data = {
        "verdict": {"decision": "Sign", "reason": "Standard terms."},
        "overall_risk": "low",
        "summary": "A benign agreement.",
        "risks": [{"title": "Minor risk", "severity": "Low", "explanation": "..."}],
        "financial_terms": [],
        "timeline": [],
    }
    seed_agreement("test-user-id", "agmt-original1", text=text, completed=True, ai_data=ai_data)

    resp = client.post("/agreements", data={"text": text}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["agreementId"] != "agmt-original1"  # new id, not the original

    # The risk item was actually copied across to the new agreement, not just
    # a status flag flipped.
    copied = dynamo_table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": f"AGREEMENT#{body['agreementId']}"},
    )["Items"]
    risk_items = [i for i in copied if i["SK"].startswith("RISK#")]
    assert len(risk_items) == 1
    assert risk_items[0]["title"] == "Minor risk"


def test_different_text_does_not_dedup(client, auth_headers, seed_agreement):
    seed_agreement("test-user-id", "agmt-original2", text="Text A", completed=True, ai_data={})

    resp = client.post("/agreements", data={"text": "Completely different text B"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "UPLOADED"  # not served from cache


# ---------------------------------------------------------------------------
# Ownership isolation
# ---------------------------------------------------------------------------

def test_user_cannot_read_another_users_agreement(client, make_token, seed_agreement):
    seed_agreement("owner-user", "agmt-private1", completed=True, ai_data={})

    attacker_token = make_token(sub="attacker-user")
    resp = client.get(
        "/agreements/agmt-private1", headers={"Authorization": f"Bearer {attacker_token}"}
    )
    assert resp.status_code == 404


def test_list_agreements_only_returns_callers_own(client, make_token, seed_agreement):
    seed_agreement("owner-user", "agmt-owned", completed=False)
    seed_agreement("other-user", "agmt-not-owned", completed=False)

    token = make_token(sub="owner-user")
    resp = client.get("/agreements", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    ids = [item["agreementId"] for item in resp.json()]
    assert ids == ["agmt-owned"]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_removes_dynamo_item_and_s3_object(client, auth_headers, seed_agreement, dynamo_table, s3_bucket):
    s3_key = seed_agreement("test-user-id", "agmt-todelete", completed=True, ai_data={})

    resp = client.delete("/agreements/agmt-todelete", headers=auth_headers)
    assert resp.status_code == 200

    get_resp = client.get("/agreements/agmt-todelete", headers=auth_headers)
    assert get_resp.status_code == 404

    with pytest.raises(Exception):
        s3_bucket.get_object(Bucket="clauseiq-test-bucket", Key=s3_key)


def test_delete_also_removes_public_share_snapshots(client, auth_headers, seed_agreement, s3_bucket):
    """
    A share link's public snapshot (SHARE#{id}) lives outside the agreement's
    own PK, so deleting the agreement must also sweep it up via the
    SHARELINK# index item written by share.py -- otherwise the public chat
    transcript stays reachable forever after the source document is gone.
    """
    seed_agreement("test-user-id", "agmt-shareddelete", completed=True, ai_data={})

    share_resp = client.post("/agreements/agmt-shareddelete/share", headers=auth_headers)
    assert share_resp.status_code == 200
    share_id = share_resp.json()["share_id"]

    assert client.get(f"/share/{share_id}").status_code == 200

    del_resp = client.delete("/agreements/agmt-shareddelete", headers=auth_headers)
    assert del_resp.status_code == 200

    assert client.get(f"/share/{share_id}").status_code == 404


# ---------------------------------------------------------------------------
# get_analysis: a real bug found while writing these tests
# ---------------------------------------------------------------------------

def test_is_legal_document_field_survives_the_full_write_and_read_path(client, auth_headers, seed_agreement):
    """
    worker/prompt.py instructs Nova to return is_legal_document: false for
    non-legal documents (e.g. test_docs' recipe edge case), and the frontend
    (DashboardPage.tsx) branches on analysis.is_legal_document === false to
    show a "not a legal document" state.

    This exercises the REAL write path: worker/dynamo.py's
    write_analysis_results() (called via the seed_agreement fixture, exactly
    as worker/worker.py calls it) followed by the REAL read path,
    api/routers/agreements.py's get_analysis().
    """
    seed_agreement(
        "test-user-id",
        "agmt-nonlegal",
        completed=True,
        ai_data={
            "is_legal_document": False,
            "verdict": {"decision": "Not a Legal Document", "reason": "This is a recipe."},
            "overall_risk": "low",
            "summary": "This document is a recipe, not a legal agreement.",
        },
    )

    resp = client.get("/agreements/agmt-nonlegal/analysis", headers=auth_headers)
    assert resp.status_code == 200
    # Regression guard: write_analysis_results() previously dropped
    # is_legal_document when writing the #ANALYSIS item, so this always
    # silently read back as True regardless of what Nova decided -- the
    # non-legal-document UI banner could never fire from real data.
    assert resp.json()["is_legal_document"] is False
