import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def verify_api_key(key: str = Security(api_key_header)) -> str:
    expected = os.environ.get("API_KEY")
    if not expected or key != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key
