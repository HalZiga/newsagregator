from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Annotated
from datetime import datetime

class Role(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    login: str
    FIO: Optional[str] = None
    phone: Optional[str] = None
    email: EmailStr
    in_ban: Optional[bool] = False

    class Config:
        from_attributes = True

class UserCreate(UserBase):
    password: str
    role_ids: Annotated[List[int], Field(default_factory=list)]

class User(UserBase):
    id: int
    created: datetime
    roles: Annotated[List[Role], Field(default_factory=list)]

class UserLogin(BaseModel):
    login: str
    password: str



