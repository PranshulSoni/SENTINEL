"""API Key authentication dependency for Sentinel."""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def require_api_key(api_key: str = Security(api_key_header)) -> str:
    settings = get_settings()
    if not settings.api_key:
        return "dev-mode"  # bypass when no key configured (local dev)
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
