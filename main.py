import os
from typing import List, Annotated, Optional
from sqlalchemy.orm import Session
from web.model_news import Role as RoleModel, User as UserModel, RoleEnum, NewsStatusEnum, WebNews, TagEnum
from web.schemes import Role, User, UserCreate, Token, News, NewsCreate, NewsUpdate
from web.database import get_db, Base, engine, SessionLocal
from web.Guard import create_access_token, get_current_user, role_required
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from web.routers.users import router as user_router
from web.routers.news import router as news_router
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Выполняется при запуске приложения и при его завершении.
    Создает таблицы БД и начальные данные (роли, админ-пользователь), если их нет.
    """
    print("Запуск приложения, БД и начальных данных")

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        for role_enum_member in RoleEnum:
            existing_role = db.query(RoleModel).filter(RoleModel.name == role_enum_member).first()
            if not existing_role:
                new_role = RoleModel(name=role_enum_member)  # Передаем член Enum напрямую
                db.add(new_role)
                print(f"Добавлена роль: {role_enum_member.value}")
        db.commit()

        # Создание админ-пользователя
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "adminpass")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")

        if not db.query(UserModel).filter(UserModel.login == admin_username).first():
            admin_role = db.query(RoleModel).filter(RoleModel.name == RoleEnum.Admin).first()
            if admin_role:

                new_admin_user = UserModel(
                    login=admin_username,
                    email=admin_email,
                    password=admin_password,  # Замените на hashed_password в реальном приложении
                    FIO="Главный Администратор",
                    phone="1234567890",
                    in_ban=False,
                    roles=[admin_role]
                )
                db.add(new_admin_user)
                db.commit()
                print(f"Создан пользователь Admin: {new_admin_user.login}")
            else:
                print("Роль 'admin' не найдена, не удалось создать администратора. Убедитесь, что роли созданы.")
        else:
            print(f"Пользователь '{admin_username}' уже существует.")

    except Exception as e:
        db.rollback()
        print(f"Ошибка при инициализации БД: {e}")
    finally:
        db.close()

    yield
    print("Завершаем приложение")

app = FastAPI(lifespan=lifespan)
app.include_router(user_router)
app.include_router(news_router)

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
def get_roles(db: Session = Depends(get_db)):
    return db.query(RoleModel).all()

def get_user_by_login(db: Session, login: str):
    return db.query(UserModel).filter(UserModel.login == login).first()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    user = get_user_by_login(db, form_data.username) # Используем form_data.username

    if not user or user.password != form_data.password:
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

    access_token = create_access_token(
        data={"sub": user.login, "roles": [role.name.value for role in user.roles]},
    )
    return {"access_token": access_token, "token_type": "bearer"}