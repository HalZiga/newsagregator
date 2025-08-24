import logging
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from web.Guard import hash_password
from web.model_news import Role as RoleModel
from web.model_news import RoleEnum
from web.model_news import User as UserModel

logger = logging.getLogger(__name__)

load_dotenv()


async def initialize_database(db: AsyncSession):
    """
    Создает начальные роли и пользователя-администратора.
    Логика обработки ошибок вынесена на уровень main.py.
    """
    for role_enum_member in RoleEnum:
        existing_role_result = await db.execute(
            select(RoleModel).where(RoleModel.name.is_(role_enum_member))
        )
        existing_role = existing_role_result.unique().scalars().one_or_none()
        if not existing_role:
            new_role = RoleModel(name=role_enum_member)
            db.add(new_role)
            logger.info(f"Добавлена роль: {role_enum_member.value}")

    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "adminpass")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")

    result = await db.execute(
        select(UserModel).where(UserModel.login.is_(admin_username))
    )
    existing_user = result.unique().scalars().one_or_none()

    if not existing_user:
        admin_role_result = await db.execute(
            select(RoleModel).where(RoleModel.name.is_(RoleEnum.Admin))
        )
        admin_role = admin_role_result.unique().scalars().one_or_none()
        if admin_role:
            hashed_password = hash_password(admin_password)
            new_admin_user = UserModel(
                login=admin_username,
                email=admin_email,
                password=hashed_password,
                FIO="Главный Администратор",
                phone="1234567890",
                in_ban=False,
                roles=[admin_role],
            )
            db.add(new_admin_user)
            logger.info(f"Создан пользователь Admin: {new_admin_user.login}")
        else:
            logger.info("Роль 'admin' не найдена, не удалось создать администратора.")
    else:
        logger.info(f"Пользователь '{admin_username}' уже существует.")
