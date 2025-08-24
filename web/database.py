import logging
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)
# DATABASE_URL = "postgresql+asyncpg://first_user:11223344@localhost:5432/news"
#
# engine = create_async_engine(DATABASE_URL) #асинхронный движок сделал

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./news.db")

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)  #

Base = declarative_base()


async def get_db():
    async with SessionLocal() as session:
        yield session
