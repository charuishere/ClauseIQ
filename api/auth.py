import os
import requests
from jose import jwt, JWTError
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
APP_CLIENT_ID = os.environ["COGNITO_APP_CLIENT_ID"]
JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"

# Cache JWKS at cold start — never re-fetch per request
_jwks = None

def get_jwks():
    global _jwks
    if _jwks is None:
        _jwks = requests.get(JWKS_URL).json()["keys"]
    return _jwks

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        # Decode header only (unverified) to get kid
        headers = jwt.get_unverified_headers(token)
        kid = headers["kid"]

        # Find matching public key
        jwks = get_jwks()
        key = next((k for k in jwks if k["kid"] == kid), None)
        if key is None:
            raise HTTPException(status_code=401, detail="Public key not found")

        # Verify and decode
        claims = jwt.decode(
            token,
            key, # public key downloaded from AWS
            algorithms=["RS256"],
            audience=APP_CLIENT_ID,
            options={"verify_exp": True}
        )

        # Validate claims
        expected_iss = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
        if claims.get("iss") != expected_iss:
            raise HTTPException(status_code=401, detail="Invalid issuer")
        if claims.get("token_use") != "id":
            raise HTTPException(status_code=401, detail="Not an ID token")

        return {"userId": claims["sub"], "email": claims.get("email", "")}

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
