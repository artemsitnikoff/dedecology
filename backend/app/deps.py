from fastapi import Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from .database import get_db
from .core.security import decode_token
from .core.errors import InvalidCredentialsError, UserInactiveError
from .models import User

oauth2_scheme = HTTPBearer()


async def get_current_user(
    token=Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Достаёт текущего пользователя по access-токену (Bearer)."""
    try:
        payload = decode_token(token.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise InvalidCredentialsError()

        # Это должен быть именно access-токен, не refresh
        if payload.get("type") != "access":
            raise InvalidCredentialsError()

        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise InvalidCredentialsError()

    except ValueError:
        raise InvalidCredentialsError()

    result = await session.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise UserInactiveError()

    return user
