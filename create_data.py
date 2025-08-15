import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from web.database import engine, get_db
from web.model_news import WebNews as News, User, Role, RoleEnum
from web.schemes import NewsStatusEnum
from web.database import Base
from web.Guard import hash_password  # Импортируем функцию из Guard.py


async def create_users_and_news(session: AsyncSession):
    """
    Создает роли, четырех пользователей: админа, модератора, двух читателей,
    и затем создает четыре новости для reader2_user.
    """
    # Сначала проверяем и создаем необходимые роли, если их нет
    roles = {role_enum: await session.scalar(select(Role).where(Role.name == role_enum)) for role_enum in RoleEnum}

    for role_enum, role_obj in roles.items():
        if not role_obj:
            new_role = Role(name=role_enum)
            session.add(new_role)
            await session.flush()  # Используем flush для получения id
            roles[role_enum] = new_role

    await session.commit()

    # Создаем пользователей
    admin_user = User(
        login="dadmin",
        password=hash_password("dadminpass"),
        email="dadmin@example.com",
    )
    admin_user.roles.append(roles[RoleEnum.Admin])

    moderator_user = User(
        login="moderator",
        password=hash_password("moderpass"),
        email="moderator@example.com",
    )
    moderator_user.roles.append(roles[RoleEnum.Moderator])

    reader1_user = User(
        login="reader1",
        password=hash_password("reader1pass"),
        email="reader1@example.com",
    )
    reader1_user.roles.append(roles[RoleEnum.Reader])

    # Reader2 будет и читателем, и автором
    reader2_user = User(
        login="reader2",
        password=hash_password("reader2pass"),
        email="reader2@example.com",
    )
    reader2_user.roles.append(roles[RoleEnum.Reader])
    reader2_user.roles.append(roles[RoleEnum.Author])

    session.add_all([admin_user, moderator_user, reader1_user, reader2_user])
    await session.commit()

    # Теперь создаем новости для reader2_user, используя `created_by_user_id`
    await session.refresh(reader2_user)

    news1 = News(
        title="Опубликованная новость 1",
        body="Это первая новость, которую написал reader2.",
        tags=["новости", "технологии"],
        status=NewsStatusEnum.Published,
        created_by_user_id=reader2_user.id,
    )
    news2 = News(
        title="Опубликованная новость 2",
        body="Это вторая новость, которую написал reader2.",
        tags=["программирование", "python"],
        status=NewsStatusEnum.Published,
        created_by_user_id=reader2_user.id,
    )
    news3 = News(
        title="Черновик новости 1",
        body="Это третья новость, которая еще не опубликована.",
        tags=["черновик"],
        status=NewsStatusEnum.Draft,
        created_by_user_id=reader2_user.id,
    )
    news4 = News(
        title="Черновик новости 2",
        body="Это четвертая новость, которая также не опубликована.",
        tags=["черновик", "обновление"],
        status=NewsStatusEnum.Draft,
        created_by_user_id=reader2_user.id,
    )

    session.add_all([news1, news2, news3, news4])
    await session.commit()

    print("Создано 4 пользователя и 4 новости.")


async def main():
    # Создаем таблицы, если их нет
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    db_gen: AsyncGenerator[AsyncSession, None] = get_db()
    session = await anext(db_gen)

    try:
        await create_users_and_news(session)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
