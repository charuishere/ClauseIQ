"""
Auth flow tests against the real verification code in api/auth.py, via the
protected /me endpoint. Tokens are signed with a throwaway RSA keypair
(see conftest.py's mock_jwks/make_token fixtures) -- no network call to
Cognito ever happens.
"""


def test_valid_token_returns_user_id(client, auth_headers):
    resp = client.get("/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"userId": "test-user-id"}


def test_missing_authorization_header_is_rejected(client):
    resp = client.get("/me")
    assert resp.status_code == 401


def test_malformed_token_is_rejected(client):
    resp = client.get("/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401


def test_expired_token_is_rejected(client, make_token):
    token = make_token(exp_offset_seconds=-3600)  # expired one hour ago
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_wrong_audience_is_rejected(client, make_token):
    token = make_token(aud="some-other-app-client-id")
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_wrong_issuer_is_rejected(client, make_token):
    token = make_token(iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_ATTACKERPOOL")
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_access_token_instead_of_id_token_is_rejected(client, make_token):
    """
    auth.py explicitly requires token_use == "id" (Cognito's access tokens
    carry token_use == "access" and lack the email claim). A signed, correctly
    issued access token must still be rejected.
    """
    token = make_token(token_use="access")
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_unknown_kid_is_rejected(client, make_token):
    """A token signed with a kid that isn't in the (fake) JWKS at all."""
    token = make_token(kid="some-kid-not-in-jwks")
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_health_endpoint_requires_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
