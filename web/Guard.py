import logging
import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from web.database import get_db
from web.model_news import User
from web.schemes import User as UserPydantic

logger = logging.getLogger(__name__)
load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")


# Функция для хеширования пароля
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Функция для проверки пароля
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> Optional[UserPydantic]:
    if not token:
        logger.warning("Отсутствует токен.")
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Токен не содержит данных пользователя",
            )
        logger.info(f"Токен успешно декодирован для пользователя: {username}")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_result = await db.execute(
        select(User).options(joinedload(User.roles)).where(User.login.is_(username))
    )
    user = user_result.scalars().unique().one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден"
        )
    return UserPydantic.model_validate(user)


def role_required(required_roles: List[str]):
    async def role_checker(
        current_user: User = Depends(get_current_user),
        token: str = Depends(oauth2_scheme),
    ):
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Не передан токен"
            )
        logger.debug(
            "Начало проверки ролей для пользователя"
            f" '{current_user.login}'. Требуемые роли: {required_roles}"
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_roles_from_token: List[str] = payload.get("roles", [])
        user_roles_names = [role for role in user_roles_from_token]
        if not any(role in required_roles for role in user_roles_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции",
            )
        logger.info(
            f"Пользователь '{current_user.login}' авторизован"
            " с ролями {user_roles_names}."
        )
        return current_user

    return role_checker
