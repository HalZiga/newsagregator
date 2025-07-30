from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Annotated
from datetime import datetime
from web.model_news import RoleEnum, NewsStatusEnum, TagEnum

class Role(BaseModel):
    name: RoleEnum

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
    role_ids: Annotated[list[int], Field(default_factory=list)]

class User(UserBase):
    id: int
    created: datetime
    roles: Annotated[list[Role], Field(default_factory=list)]

class UserLogin(BaseModel):
    login: str
    password: str

class UserForModerator(BaseModel):
    id: int
    login: str
    FIO: str
    in_ban: bool
    created: datetime
    roles: list[Role]

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    login: Optional[str] = Field(None, min_length=3, max_length=50)
    FIO: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    in_ban: Optional[bool] = False
    role_ids: Annotated[list[int], Field(default_factory=list)] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
    roles: list[str] = []

class NewsBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    body: str = Field(..., min_length=10)
    status: NewsStatusEnum

class NewsCreate(NewsBase):
    pass

class NewsUpdate(NewsBase):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    body: Optional[str] = Field(None, min_length=10)


class News(NewsBase):
    id: int
    created_by_user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    URL: Optional[str] = None
    author: Optional[str] = None
    status: NewsStatusEnum
    tags: set[str] = Field(default_factory=set)
    category: Optional[TagEnum] = None
    views: int = 0

    class Config:
        from_attributes = True