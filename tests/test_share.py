"""
Tests for api/routers/share.py: ownership enforcement on link creation,
and the deliberately-unauthenticated public retrieval endpoint.
"""


def test_create_share_link_requires_ownership(client, make_token, seed_agreement):
    seed_agreement("owner-user", "agmt-shareme", completed=True, ai_data={})

    attacker_token = make_token(sub="attacker-user")
    resp = client.post(
        "/agreements/agmt-shareme/share", headers={"Authorization": f"Bearer {attacker_token}"}
    )
    assert resp.status_code == 404


def test_create_and_publicly_retrieve_share_snapshot(client, auth_headers, seed_agreement, dynamo_table):
    seed_agreement("test-user-id", "agmt-shareme2", completed=True, ai_data={})

    # Seed one chat message the way chat.py would persist it, so the
    # snapshot has something real to carry across.
    dynamo_table.put_item(
        Item={
            "PK": "AGREEMENT#agmt-shareme2",
            "SK": "CHAT#1",
            "messageId": "chat-1",
            "question": "What is the termination notice period?",
            "answer": "30 days.",
            "answer_type": "document",
            "citations": [],
            "found_in_document": True,
        }
    )

    create_resp = client.post("/agreements/agmt-shareme2/share", headers=auth_headers)
    assert create_resp.status_code == 200
    share_id = create_resp.json()["share_id"]

    # Deliberately no Authorization header -- this is the public route.
    public_resp = client.get(f"/share/{share_id}")
    assert public_resp.status_code == 200
    body = public_resp.json()
    assert body["agreement_id"] == "agmt-shareme2"
    assert len(body["messages"]) == 1
    assert body["messages"][0]["question"] == "What is the termination notice period?"


def test_get_unknown_share_id_returns_404(client, dynamo_table):
    resp = client.get("/share/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
