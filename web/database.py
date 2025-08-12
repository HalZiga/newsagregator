from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://first_user:11223344@localhost:5432/news"

engine = create_async_engine(DATABASE_URL) #асинхронный движок сделал

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession) #

Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session