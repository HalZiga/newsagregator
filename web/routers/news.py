from sqlalchemy.ext.asyncio import AsyncSession
from web.model_news import User as UserModel, TagEnum, RoleEnum, NewsStatusEnum
from web.database import get_db
from web.schemes import News, NewsCreate, NewsUpdate, NewsWithPermission
from web.Guard import get_current_user, role_required
from fastapi import APIRouter, Depends, status
from typing import List, Optional, Annotated
from web.services.news_service import (
    create_news_service, get_published_news_service, get_all_news_authorized_service, get_news_by_id_service,
    update_news_service, publish_news_service, delete_news_service
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

@router.get("/categories", response_model=list[str])
async def get_available_categories():
    """
    Возвращает список всех доступных категорий новостей.
    """
    return [tag.value for tag in TagEnum]

@router.post("/", response_model=News, status_code=status.HTTP_201_CREATED)
async def create_news(
        news_data: NewsCreate,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(role_required([RoleEnum.Admin.value, RoleEnum.Moderator.value, RoleEnum.Author.value, RoleEnum.Reader.value]))
):
    new_news = await create_news_service(news_data=news_data, db=db, current_user=current_user)
    return News.model_validate(new_news)


@router.get("/published", response_model=List[News])
async def get_published_news(
        db: AsyncSession = Depends(get_db)
):
    """
    Получить список всех опубликованных новостей. Доступно всем без авторизации.
    """
    news_list = await get_published_news_service(db=db)
    return [News.model_validate({**item.__dict__,
    "author": item.created_by.login}) for item in news_list]


@router.get("/", response_model=list[News])
async def get_all_news_authorized(
        db: AsyncSession = Depends(get_db),
        current_user: Optional[UserModel] = Depends(get_current_user)
):
    """
    Получить все доступные новости авторизованному пользователю.
    """

    news_list = await get_all_news_authorized_service(db=db, current_user=current_user)

    return [News.model_validate({**item.__dict__,
        "author": item.created_by.login})for item in news_list]

@router.get("/{news_id}", response_model=NewsWithPermission)
async def get_news_by_id(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_current_user)
):
    logger.info("Пользователь '%s' запрашивает новость с ID: %d",
                current_user.login if current_user else "Неавторизованный пользователь", news_id)
    news_data = await get_news_by_id_service(news_id, db, current_user)

    current_user_data = news_data.pop("current_user", None)
    user_roles = current_user_data["roles"] if current_user_data else []

    is_moderator = RoleEnum.Moderator.value in user_roles
    is_admin = RoleEnum.Admin.value in user_roles
    is_author = bool(current_user_data) and news_data["created_by_user_id"] == current_user_data["id"]

    can_publish_value = is_moderator and news_data["status"] == NewsStatusEnum.Draft
    can_delete_update_value = is_moderator or is_admin or is_author

    return NewsWithPermission.model_validate({
        **news_data,
        "can_publish": can_publish_value,
        "can_delete_update": can_delete_update_value
    })


@router.patch("/{news_id}", response_model=News)
async def update_news(
        news_id: int,
        news_data: NewsUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(role_required([RoleEnum.Admin.value, RoleEnum.Moderator.value, RoleEnum.Author.value]))
):
    """
    Обновить существующую новость.
    Автор может обновлять только свои новости. Админ/модератор могут обновлять любые.
    """
    logger.info("метод по обновлению новости начнется")
    updated_news = await update_news_service(news_id=news_id, news_data=news_data, db=db, current_user=current_user)
    logger.info("метод по обновлению новости завершен")
    # updated_news = await get_news_by_id(news_id=news_id, db=db, current_user=current_user)
    # logger.info("возвращение данных завершено")
    return News.model_validate(updated_news)


@router.patch("/publish/{news_id}", response_model=News)
async def publish_news(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Annotated[UserModel, Depends(get_current_user)] = None
):
    """
    Опубликовать новость. Только для модераторов и администраторов.
    """
    published_news = await publish_news_service(news_id=news_id, db=db, current_user=current_user)
    return News.model_validate(published_news)

@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news(
        news_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(role_required([RoleEnum.Admin.value, RoleEnum.Moderator.value, RoleEnum.Author.value]))
):
    """
    Удалить новость по ID. Доступно только для 'admin' и 'moderator'.
    """
    await delete_news_service(news_id=news_id, db=db, current_user=current_user)
    return {}

