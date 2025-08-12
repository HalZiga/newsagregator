from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from typing import List
from web.model_news import User as UserModel, Role as RoleModel, RoleEnum
from web.schemes import UserUpdate, UserCreate
from web.Guard import hash_password
from fastapi import HTTPException, status
from datetime import datetime, timezone

async def get_all_roles_service(db: AsyncSession) -> List[RoleModel]:
    result = await db.execute(select(RoleModel))
    return list(result.scalars().all())

async def get_user_by_login(db: AsyncSession, login: str) -> UserModel:
    result = await db.execute(select(UserModel).where(UserModel.login == login).options(joinedload(UserModel.roles)))
    return result.unique().scalar_one_or_none()

async def create_new_user(user: UserCreate, db: AsyncSession) -> UserModel:
    """
    Бизнес-логика для создания нового пользователя.
    """
    reader_role_result = await db.execute(select(RoleModel).where(RoleModel.name == RoleEnum.Reader))
    reader_role = reader_role_result.scalar_one_or_none()
    if not reader_role:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Роль 'Reader' не найдена.")

    existing_user_result = await db.execute(select(UserModel).where(UserModel.login == user.login))
    existing_user = existing_user_result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Логин уже занят")

    hashed_password = hash_password(user.password)

    user_obj = UserModel(
        login=user.login,
        FIO=user.FIO,
        phone=user.phone,
        email=user.email,
        in_ban=False,
        created=datetime.now(timezone.utc).replace(tzinfo=None),
        roles=[reader_role],
        password=hashed_password
    )

    db.add(user_obj)
    await db.commit()
    await db.refresh(user_obj)

    user_with_roles = await db.execute(
        select(UserModel)
        .where(UserModel.id == user_obj.id)
        .options(joinedload(UserModel.roles))
    )
    return user_with_roles.unique().scalar_one_or_none()

async def update_user_data(
    user_id: int,
    user_update: UserUpdate,
    db: AsyncSession,
    current_user: UserModel
) -> UserModel:
    """
    Обновляет данные пользователя с проверками прав доступа.
    Бизнес-логика вынесена из роута.
    """
    user_to_update_result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user_to_update = user_to_update_result.scalar_one_or_none()
    if not user_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    user_roles = [role.name.value for role in current_user.roles]

    if "admin" not in user_roles and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Недостаточно прав для редактирования этого пользователя")

    if "admin" not in user_roles:
        if user_update.role_ids is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Только администраторы могут изменять роли")
        if user_update.in_ban is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Только администраторы могут изменять статус блокировки")

    update_data = user_update.model_dump(exclude_unset=True)

    if "role_ids" in update_data:
        new_roles_result = await db.execute(select(RoleModel).where(RoleModel.id.in_(update_data["role_ids"])))
        new_roles = new_roles_result.scalars().all()
        if not new_roles and update_data["role_ids"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Одна или несколько указанных ролей не найдены")
        user_to_update.roles = new_roles
        del update_data["role_ids"]

    for key, value in update_data.items():
        setattr(user_to_update, key, value)

    db.add(user_to_update)
    await db.commit()
    await db.refresh(user_to_update)
    return user_to_update

async def get_users_list(db: AsyncSession, current_user: UserModel) -> List[UserModel]:
    """
    Бизнес-логика для получения списка пользователей с учетом прав.
    """
    user_roles = [role.name.value for role in current_user.roles]

    if "admin" in user_roles or "moderator" in user_roles:
        result = await db.execute(select(UserModel).options(joinedload(UserModel.roles)))
        return result.scalars().unique().all()
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Недостаточно прав для просмотра списка пользователей")


async def get_user_by_id_service(user_id: int, db: AsyncSession, current_user: UserModel) -> UserModel:
    """
    Бизнес-логика для получения одного пользователя с учетом прав.
    """
    user_roles = [role.name.value for role in current_user.roles]
    user_result = await db.execute(select(UserModel).options(joinedload(UserModel.roles)).where(UserModel.id == user_id))
    user = user_result.unique().scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if "admin" in user_roles or "moderator" in user_roles or current_user.id == user_id:
        return user
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Недостаточно прав для просмотра этого пользователя")


async def update_user_ban_status_service(user_id: int, in_ban: bool, db: AsyncSession, current_user: UserModel) -> UserModel:
    """
    Бизнес-логика для изменения статуса бана.
    """
    user_to_update_result = await db.execute(select(UserModel).options(joinedload(UserModel.roles)).where(UserModel.id == user_id))
    user_to_update = user_to_update_result.unique().scalar_one_or_none()
    if not user_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if user_to_update.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Вы не можете изменить статус блокировки для самого себя.")

    if user_to_update.in_ban == in_ban:
        return user_to_update

    user_to_update.in_ban = in_ban
    user_to_update.updated = datetime.now(timezone.utc).replace(tzinfo=None)

    db.add(user_to_update)
    await db.commit()
    await db.refresh(user_to_update)
    return user_to_update


async def delete_user_service(user_id: int, db: AsyncSession) -> None:
    """
    Бизнес-логика для удаления пользователя.
    """
    user_result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    await db.delete(user)
    await db.commit()