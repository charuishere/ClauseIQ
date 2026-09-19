import os
import requests
from jose import jwt, JWTError
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
APP_CLIENT_ID = os.environ["COGNITO_APP_CLIENT_ID"]
COGNITO_ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

# Cache JWKS across warm invocations, but allow a forced refresh below --
# Cognito can rotate its signing keys, and a cached set from before a
# rotation would otherwise reject valid tokens until the Lambda cold-starts.
_jwks = None

def get_jwks(force_refresh: bool = False):
    global _jwks
    if _jwks is None or force_refresh:
        try:
            _jwks = requests.get(JWKS_URL, timeout=5).json()["keys"]
        except requests.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Unable to fetch auth keys: {e}")
    return _jwks

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        # Decode header only (unverified) to get kid
        headers = jwt.get_unverified_headers(token)
        kid = headers["kid"]

        # Find matching public key; if not found, our cached JWKS may be
        # stale from a key rotation, so force one refresh before giving up.
        jwks = get_jwks()
        key = next((k for k in jwks if k["kid"] == kid), None)
        if key is None:
            jwks = get_jwks(force_refresh=True)
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
        if claims.get("iss") != COGNITO_ISSUER:
            raise HTTPException(status_code=401, detail="Invalid issuer")
        if claims.get("token_use") != "id":
            raise HTTPException(status_code=401, detail="Not an ID token")

        return {"userId": claims["sub"], "email": claims.get("email", "")}

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
