from fastapi import Header, HTTPException, status
from .config import settings

async def verify_password(x_app_password: str = Header(None)):
    if x_app_password != settings.APP_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing password",
        )
