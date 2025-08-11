from sqlalchemy.orm import Session, joinedload
from web.model_news import User as UserModel, NewsStatusEnum, WebNews, TagEnum, RoleEnum, Role
from web.database import get_db
from web.schemes import News, NewsCreate, NewsUpdate, NewsWithPermission
from web.Guard import get_current_user, role_required
from sqlalchemy import or_
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from dotenv import load_dotenv
from typing import List, Optional, Annotated

load_dotenv()

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
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(role_required(["admin", "moderator", "author", "reader"]))
):
    news_status = NewsStatusEnum.Draft
    author_role = db.query(Role).filter(Role.name == RoleEnum.Author).first()

    new_news = WebNews(
        title=news_data.title,
        body=news_data.body,
        status=news_status,
        created_by_user_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        tags=news_data.tags,
        category=news_data.category
    )
    db.add(new_news)

    user_has_author_role = any(role.name == 'author' for role in current_user.roles)
    if not user_has_author_role:
        current_user.roles.append(author_role)
    db.commit()
    db.refresh(new_news)

    return News.model_validate(new_news)


@router.get("/published", response_model=List[News])
async def get_published_news(
        db: Session = Depends(get_db)
):
    """
    Получить список всех опубликованных новостей. Доступно всем без авторизации.
    """
    published_news = db.query(WebNews).filter(WebNews.status == NewsStatusEnum.Published).order_by(
        WebNews.published_at.desc()).options(joinedload(WebNews.created_by)).all()

    return [News.model_validate(item) for item in published_news]


@router.get("/", response_model=list[News])
async def get_all_news_authorized(
        db: Session = Depends(get_db),
        current_user: Optional[UserModel] = Depends(get_current_user)
):
    """
    Получить все доступные новости авторизованному пользователю.
    """
    user_roles_names = [role.name.value for role in current_user.roles] if current_user and current_user.roles else []
    query = db.query(WebNews).options(joinedload(WebNews.created_by))

    if current_user and ("admin" in user_roles_names or "moderator" in user_roles_names):
        news_list = query.order_by(WebNews.created_at.desc()).all()
    elif current_user:
        news_list = query.filter(
            or_(
                WebNews.status == NewsStatusEnum.Published,
                WebNews.created_by_user_id == current_user.id
            )
        ).order_by(WebNews.created_at.desc()).all()
    else:
        news_list = query.filter(WebNews.status == NewsStatusEnum.Published).order_by(WebNews.created_at.desc()).all()

    return news_list

@router.get("/{news_id}", response_model=NewsWithPermission)
async def get_news_by_id(
        news_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserModel] = Depends(get_current_user)
):
    news = db.query(WebNews).options(joinedload(WebNews.created_by)).filter(WebNews.id == news_id).first()
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")

    user_roles = [role.name.value for role in current_user.roles] if current_user else []

    if news.status != NewsStatusEnum.Published:
        if not current_user or (
                "admin" not in user_roles and
                "moderator" not in user_roles and
                current_user.id != news.created_by_user_id
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этой новости")

    news.views += 1
    db.add(news)
    db.commit()
    db.refresh(news)

    is_moderator = RoleEnum.Moderator.value in user_roles
    is_draft = news.status == NewsStatusEnum.Draft
    can_publish_value = is_moderator and is_draft

    is_admin = RoleEnum.Admin.value in user_roles
    is_author_of_this_news = current_user is not None and current_user.id == news.created_by_user_id
    can_delete_update_value = is_moderator or is_admin or is_author_of_this_news

    news_data = {
        "id": news.id,
        "title": news.title,
        "body": news.body,
        "status": news.status,
        "created_by_user_id": news.created_by_user_id,
        "created_at": news.created_at,
        "URL": news.URL,
        "tags": news.tags,
        "category": news.category,
        "views": news.views,
        "created_by": news.created_by,
        "can_publish": can_publish_value,
        "can_delete_update": can_delete_update_value,
    }

    return NewsWithPermission.model_validate(news_data)


@router.patch("/{news_id}", response_model=News)
async def update_news(
        news_id: int,
        news_data: NewsUpdate,
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(role_required(["admin", "moderator", "author"]))
):
    """
    Обновить существующую новость.
    Автор может обновлять только свои новости. Админ/модератор могут обновлять любые.
    """
    news = db.query(WebNews).filter(WebNews.id == news_id).first()
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")

    user_roles = [role.name.value for role in current_user.roles]

    is_admin = "admin" in user_roles
    is_moderator = "moderator" in user_roles  # Добавлено для полной проверки
    is_author_of_this_news = current_user.id == news.created_by_user_id

    if not (is_admin or is_moderator) and not is_author_of_this_news:  # ИСПРАВЛЕНО: модератор тоже может обновлять
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="У вас нет прав на редактирование этой новости.")

    update_data = news_data.model_dump(exclude_unset=True)

    # !!! ИСПРАВЛЕНО: Проверка на изменение статуса на 'Published'
    if "status" in update_data and update_data["status"] == NewsStatusEnum.Published:
        if not (is_admin or is_moderator):  # Только админ или модератор могут устанавливать статус Published
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Только администраторы или модераторы могут публиковать новости.")

    for key, value in update_data.items():
        setattr(news, key, value)

    news.redacted_at = datetime.now(timezone.utc)

    db.add(news)
    db.commit()
    db.refresh(news)

    return news


@router.patch("/publish/{news_id}", response_model=News)
async def publish_news(
    news_id: int,
    db: Session = Depends(get_db),
    current_user: Annotated[UserModel, Depends(get_current_user)] = None,
):
    """
    Опубликовать новость. Только для модераторов и администраторов.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация"
        )
    user_roles = [role.name.value for role in current_user.roles]
    if not ("admin" in user_roles or "moderator" in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для публикации новости"
        )

    news = db.query(WebNews).filter(WebNews.id == news_id).first()
    if not news:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Новость не найдена"
        )
    if news.status != NewsStatusEnum.Draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Можно публиковать только черновики"
        )

    news.status = NewsStatusEnum.Published
    news.published_at = datetime.now(timezone.utc)
    news.updated_at = datetime.now(timezone.utc)
    db.add(news)
    db.commit()
    db.refresh(news)



    return news


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news(
        news_id: int,
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(role_required(["admin", "moderator"]))
):
    """
    Удалить новость по ID. Доступно только для 'admin' и 'moderator'.
    """
    news = db.query(WebNews).filter(WebNews.id == news_id).first()
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")

    db.delete(news)
    db.commit()
    return {}

