import logging
from contextlib import asynccontextmanager
from typing import Annotated, List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from web.database import Base, SessionLocal, engine, get_db
from web.exception_handlers import (
    catch_all_exception_handler,
    http_exception_handler,
    integrity_error_handler,
    validation_exception_handler,
)
from web.Guard import create_access_token, verify_password
from web.routers.news import router as news_router
from web.routers.users import router as user_router
from web.schemes import Role, Token
from web.services.init_service import initialize_database
from web.services.user_service import get_all_roles_service, get_user_by_login

logging.basicConfig(
    level=logging.INFO, format=("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logger = logging.getLogger(__name__)

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск приложения, БД и начальных данных")
    async with engine.begin() as conn:  # асинхронный контекстный менеджер
        await conn.run_sync(
            Base.metadata.create_all
        )  # run_sync запускает в отдельном потоке
    db = SessionLocal()
    try:
        await initialize_database(db)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e
    finally:
        await db.close()
    yield
    logger.info("Завершаем приложение")


app = FastAPI(lifespan=lifespan)

app.include_router(user_router)
app.include_router(news_router)

app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, catch_all_exception_handler)


origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/roles/", response_model=List[Role])
async def get_roles(db: AsyncSession = Depends(get_db)):
    return await get_all_roles_service(db)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    logger.info("Попытка аутентификации для пользователя: %s", form_data.username)
    user = await get_user_by_login(db, form_data.username)

    if not user or not verify_password(form_data.password, user.password):
        logger.warning(
            "Неудачная попытка входа для пользователя: %s", form_data.username
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.in_ban:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ваша учетная запись заблокирована",
        )

    logger.info("Пользователь '%s' успешно аутентифицирован.", user.login)
    access_token = create_access_token(
        data={
            "sub": user.login,
            "id": user.id,
            "roles": [role.name.value for role in user.roles],
        },
    )
    return {"access_token": access_token, "token_type": "bearer"}
