from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+psycopg2://first_user:11223344@localhost:5432/news"

engine = create_engine(DATABASE_URL) #соединение

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) #

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()