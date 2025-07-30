from typing import Optional, List
from jose import JWTError, jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from web.database import get_db, Base
from web.model_news import User
from web.schemes import TokenData
import os

load_dotenv()

# class CurrentUserWithRoles(BaseModel):
#     id: int
#     login: str
#     email: str
#     roles: List[str]
#
#     class Config:
#         from_attributes = True # если часто надо будет декодировать токен надо будет сделать класс где буде хранить все


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode,  # Словарь данных
    SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if token is None:
        return None
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise None
        token_data = TokenData(username=username, roles=payload.get("roles", []))
    except JWTError:
        return None
    user = db.query(User).filter(User.login == username).first()
    if user is None:
        return None
    return user

def role_required(required_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user), token: str = Depends(oauth2_scheme)):
        if token is None:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_roles_from_token: List[str] = payload.get("roles", [])
        user_roles_names = [role for role in user_roles_from_token]
        if not any(role in required_roles for role in user_roles_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции"
            )
        return current_user
    return role_checker