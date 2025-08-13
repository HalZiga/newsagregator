from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from web.model_news import WebNews, User as UserModel, NewsStatusEnum, RoleEnum, Role
from web.schemes import NewsCreate, NewsUpdate, News
from fastapi import HTTPException, status
from datetime import datetime, timezone
from sqlalchemy import or_
import logging

logger = logging.getLogger(__name__)

async def create_news_service(news_data: NewsCreate, db: AsyncSession, current_user: UserModel) -> WebNews:
    """
    Создает новую новость и возвращает полностью загруженный объект новости.
    """
    logger.info("Создание новости от пользователя: %s", current_user.login)
    user_has_author_role = any(role.name == RoleEnum.Author for role in current_user.roles)
    if not user_has_author_role:
        author_role_result = await db.execute(select(Role).where(Role.name == RoleEnum.Author))
        author_role = author_role_result.scalar_one_or_none()

        if not author_role:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Роль 'Author' не найдена.")

        current_user.roles.append(author_role)
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        logger.info("Роль 'Author' успешно добавлена пользователю %s.", current_user.login)

    new_news = WebNews(
        title=news_data.title,
        body=news_data.body,
        status=NewsStatusEnum.Draft,
        created_by_user_id=current_user.id,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        tags=news_data.tags,
        category=news_data.category
    )
    db.add(new_news)
    await db.commit()
    await db.refresh(new_news)

    news_with_relations_result = await db.execute(
        select(WebNews)
        .where(WebNews.id == new_news.id)
        .options(joinedload(WebNews.created_by).joinedload(UserModel.roles))
    )
    news_with_relations = news_with_relations_result.unique().scalar_one_or_none()

    if not news_with_relations:
        logger.error("После создания не удалось загрузить новость с ID %d с отношениями.", new_news.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Не удалось загрузить новость с отношениями.")

    return news_with_relations


async  def get_published_news_service(db: AsyncSession) -> List[WebNews]:
    """Получает список всех опубликованных новостей."""
    result = await db.execute(
        select(WebNews).where(WebNews.status == NewsStatusEnum.Published)
        .order_by(WebNews.published_at.desc()).options(joinedload(WebNews.created_by).joinedload(UserModel.roles))
    )
    logger.info("Успешно получены опубликованные новости")
    return result.scalars().unique().all()


async def get_all_news_authorized_service(db: AsyncSession, current_user: Optional[UserModel]) -> List[WebNews]:
    """Получает все доступные новости авторизованному пользователю."""
    logger.info("Получение всех новостей")
    user_roles_names = [role.name.value for role in current_user.roles] if current_user and current_user.roles else []
    query = select(WebNews).options(joinedload(WebNews.created_by).joinedload(UserModel.roles))

    if current_user and ("admin" in user_roles_names or "moderator" in user_roles_names):
        logger.info("Пользователь %s администратор/модератор.", current_user.login)
        result = await db.execute(query.order_by(WebNews.created_at.desc()))
    elif current_user:
        logger.info("Пользователю %s возвращаем его черновики и опубликованные новости.",
        current_user.login)
        result = await db.execute(query.where(
            or_(WebNews.status == NewsStatusEnum.Published, WebNews.created_by_user_id == current_user.id)
        ).order_by(WebNews.created_at.desc()))
    else:
        logger.info("Пользователь не авторизован. Возвращаем только опубликованные новости.")
        result = await db.execute(query.where(WebNews.status == NewsStatusEnum.Published).order_by(WebNews.created_at.desc()))
    return result.scalars().unique().all()

async def get_news_by_id_service(
    news_id: int,
    db: AsyncSession,
    current_user: Optional[UserModel]
) -> dict:
    """
    Возвращает готовые данные о новости с учётом прав доступа
    и увеличением счётчика просмотров.
    Все необходимые данные подгружаются в одном запросе.
    """
    logger.info("Попытка получить новость с ID: %d для пользователя: %s", news_id,
                current_user.login if current_user else "неавторизованный пользователь")

    current_user_data = None
    if current_user:
        result_user = await db.execute(
            select(UserModel)
            .options(joinedload(UserModel.roles))
            .where(UserModel.id == current_user.id)
        )
        user_obj = result_user.unique().scalar_one_or_none()
        logger.info("Пользователь автаризован загрузили его данные")
        if user_obj:
            current_user_data = {
                "id": user_obj.id,
                "roles": [role.name.value for role in user_obj.roles]
            }
            logger.info("Загрузка ролей пользователся успешна")



    result_news = await db.execute(
        select(WebNews)
        .options(
            joinedload(WebNews.created_by).joinedload(UserModel.roles)
        )
        .where(WebNews.id == news_id)
    )
    news = result_news.unique().scalar_one_or_none()

    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")
    logger.info("Загрузка новости вместе с создателем и ролями создателя успешна")

    if news.status != NewsStatusEnum.Published:
        if not current_user_data or not (
            RoleEnum.Admin.value in current_user_data["roles"] or
            RoleEnum.Moderator.value in current_user_data["roles"] or
            current_user_data["id"] == news.created_by_user_id
        ):
            logger.warning("Пользователь %s попытался получить доступ к неопубликованной новости с ID %d без прав.",
                           current_user.login if current_user else "неавторизованный пользователь", news_id)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этой новости")
    logger.info("Проверка прав успешна")

    response_data = {
        "id": news.id,
        "title": news.title,
        "body": news.body,
        "status": news.status,
        "created_by_user_id": news.created_by_user_id,
        "created_at": news.created_at,
        "URL": news.URL,
        "tags": news.tags,
        "category": news.category,
        "views": news.views + 1,
        "created_by": {
            "id": news.created_by.id,
            "login": news.created_by.login,
            "roles": [{"id": role.id, "name": role.name.value} for role in news.created_by.roles]
        },
        "current_user": current_user_data
    }

    news.views += 1
    news.redacted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(news)
    await db.commit()

    return response_data



async def update_news_service(news_id: int, news_data: NewsUpdate, db: AsyncSession, current_user: UserModel) -> WebNews:
    """Обновляет существующую новость с проверкой прав."""
    logger.info("Пользователь %s пытается обновить новость с Id: %d", current_user.login, news_id)
    news_result = await db.execute(select(WebNews).options(joinedload(WebNews.created_by).joinedload(UserModel.roles)).where(WebNews.id == news_id))
    news = news_result.unique().scalar_one_or_none()

    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")

    user_roles = [role.name.value for role in current_user.roles]
    is_admin_or_moderator = RoleEnum.Admin.value in user_roles or RoleEnum.Moderator.value in user_roles
    is_author_of_this_news = current_user.id == news.created_by_user_id

    if not (is_admin_or_moderator or is_author_of_this_news):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="У вас нет прав на редактирование этой новости.")

    update_data = news_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(news, key, value)

    news.redacted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(news)
    await db.commit()
    await db.refresh(news)
    logger.info("Новость с ID %d успешно обновлена пользователем %s.", news_id, current_user.login)

    return news


async def publish_news_service(news_id: int, db: AsyncSession, current_user: UserModel) -> WebNews:
    """Публикует новость."""
    logger.info("Пользователь %s пытается опубликовать новость с ID: %d", current_user.login, news_id)
    user_roles = [role.name.value for role in current_user.roles]
    if not (RoleEnum.Moderator.value in user_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для публикации новости")

    news_result = await db.execute(select(WebNews).options(joinedload(WebNews.created_by).joinedload(UserModel.roles)).where(WebNews.id == news_id))
    news = news_result.unique().scalar_one_or_none()

    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")
    if news.status != NewsStatusEnum.Draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Можно публиковать только черновики")

    news.status = NewsStatusEnum.Published
    news.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    news.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(news)
    await db.commit()
    await db.refresh(news)
    logger.info("Новость с ID %d успешно опубликована пользователем %s.", news_id, current_user.login)
    return news


async def delete_news_service(news_id: int, db: AsyncSession) -> None:
    """Удаляет новость."""
    logger.info("Попытка удаления новости с ID: %d", news_id)
    news_result = await db.execute(select(WebNews).where(WebNews.id == news_id))
    news = news_result.scalar_one_or_none()

    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")

    await db.delete(news)
    await db.commit()
    logger.info("Новость с ID %d успешно удалена.", news_id)