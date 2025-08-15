from pydantic import BaseModel, EmailStr, Field, computed_field
from typing import Optional, Annotated
from datetime import datetime
from web.model_news import RoleEnum, TagEnum, NewsStatusEnum

class Role(BaseModel):
    id: int
    name: RoleEnum

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    login: str
    FIO: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    in_ban: bool = False

    class Config:
        from_attributes = True

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created: datetime
    roles: Annotated[list[Role], Field(default_factory=list)] = None

class UserForNews(BaseModel):
    login: str
    roles: list[Role]

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    login: str
    password: str

class UserForModerator(BaseModel):
    id: int
    login: str
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
    in_ban: Optional[bool] = None
    role_ids: Optional[list[int]] = None

    class Config:
        from_attributes = True

class UserUpdateBanStatus(BaseModel):
    in_ban: Optional[bool] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None
    id: int
    roles: list[str] = []

class NewsBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    body: str = Field(..., min_length=10)
    tags: list[str] = Field(default_factory=list)
    category: Optional[TagEnum] = None

class NewsCreate(NewsBase):
    pass

class NewsUpdate(NewsBase):
    pass

class News(NewsBase):
    id: int
    status: NewsStatusEnum
    created_by_user_id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    URL: Optional[str] = None
    views: int = 0
    author: Optional[str] = Field(None)

    class Config:
        from_attributes = True

class NewsWithPermission(News):
    can_publish: bool
    can_delete_update: bool

    class Config:
        from_attributes = True