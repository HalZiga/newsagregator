import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum, ForeignKey, Table
from web.database import Base
from sqlalchemy.orm import relationship
from datetime import datetime

class TagEnum(enum.Enum):
    Live = "Live"
    AI = "AI"
    SCIENCE = "Science"
    POLITICS = "Politics"
    SPORT = "Sport"

class RoleEnum(enum.Enum):# 'admin', 'moderator', 'reader'
    Admin = "Admin"
    Moderator = "Moderator"
    Reader = "Reader"

class WebNews(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    URL = Column(String, unique=True)
    author = Column(String)  #мб id надо
    status = Column(Boolean, default=True) #пока так мб еще надо будет таблицу состояний
    published_at = Column(DateTime)
    redacted_at = Column(DateTime)
    tags = Column(String) #
    category = Column(Enum(TagEnum), nullable=False, default=TagEnum.Live) #
    views = Column(Integer, default=0)

user_roles = Table(
    'user_roles', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    login = Column(String(50), unique=True, nullable=False)
    FIO = Column(String(100))
    phone = Column(String(12))
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    in_ban = Column(Boolean, default=False)
    created = Column(DateTime, default=datetime.utcnow)

    roles = relationship("Role", secondary=user_roles, back_populates="users")

class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(Enum(RoleEnum), nullable=True)

    users = relationship("User", secondary=user_roles, back_populates="roles")

