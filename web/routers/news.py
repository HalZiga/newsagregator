from sqlalchemy.orm import Session
from web.model_news import  User as UserModel, NewsStatusEnum, WebNews, TagEnum
from web.database import get_db
from web.schemes import News, NewsCreate, NewsUpdate
from web.Guard import get_current_user, role_required
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

router = APIRouter(prefix="/news", tags=["news"])

@router.post("/news/", response_model=News, status_code=status.HTTP_201_CREATED)
async def create_news(
    news_data: NewsCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(role_required(["admin", "moderator", "author"]))
):

    news_status = NewsStatusEnum.Draft

    new_news = WebNews(
        title=news_data.title,
        body=news_data.body,
        status=news_status,
        created_by_user_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        tags=["First", "admin"],
        category=TagEnum.SCIENCE
    )
    db.add(new_news)
    db.commit()
    db.refresh(new_news)
    return new_news

@router.get("/news/", response_model=List[News])
async def get_all_news(
    db: Session = Depends(get_db),
    # Опциональная авторизация: если токен есть, получаем пользователя, иначе None
    current_user: Optional[UserModel] = Depends(get_current_user)
):
    """
    Получить список всех новостей.
    Опубликованные новости доступны всем.
    Черновики и архивы доступны только админам, модераторам и автору черновика.
    """
    user_roles = [role.name.value for role in current_user.roles] if current_user else []

    if "admin" in user_roles or "moderator" in user_roles:
        # Админы и модераторы видят все новости
        news_query = db.query(WebNews)
    else:
        # Все остальные видят только опубликованные новости
        news_query = db.query(WebNews).filter(WebNews.status == NewsStatusEnum.Published)

    # Если пользователь является автором, он также видит свои черновики/архивы
    if current_user and "author" in user_roles:
        news_query = news_query.union(
            db.query(WebNews).filter(WebNews.author_id == current_user.id)
        )

    return news_query.order_by(WebNews.published_at.desc()).all()


@router.get("/news/{news_id}", response_model=News)
async def get_news_by_id(
    news_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_current_user)
):
    """
    Получить новость по ID.
    Для неопубликованных новостей требуется авторизация и соответствующие права (автор/модератор/админ).
    """
    news = db.query(WebNews).filter(WebNews.id == news_id).first()
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")

    user_roles = [role.name.value for role in current_user.roles] if current_user else []

    # Проверка доступа к неопубликованным новостям
    if news.status != NewsStatusEnum.Published:
        # Если нет текущего пользователя ИЛИ текущий пользователь не админ/модератор ИЛИ он не автор этой новости
        if not current_user or (
            "admin" not in user_roles and
            "moderator" not in user_roles and
            current_user.id != news.author_id
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этой новости")

    return news


@router.patch("/news/{news_id}", response_model=News)
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

    # Проверка, может ли пользователь обновить эту новость
    is_admin_or_moderator = "admin" in user_roles or "moderator" in user_roles
    is_author_of_this_news = current_user.id == news.created_by_user_id

    if not is_admin_or_moderator and not is_author_of_this_news:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У вас нет прав на редактирование этой новости.")

    update_data = news_data.model_dump(exclude_unset=True) #только те поля, которые были переданы

    if "status" in update_data and update_data["status"] is not None:
        try:
            update_data["status"] = NewsStatusEnum[update_data["status"].upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неверный статус новости: {news_data.status}. Допустимые: {', '.join([s.value for s in NewsStatusEnum])}"
            )
        if update_data["status"] == NewsStatusEnum.Published and not is_admin_or_moderator:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только админ или модератор могут публиковать новости.")

    for key, value in update_data.items():
        setattr(news, key, value)
    news.redacted_at = datetime.now(timezone.utc)
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


@router.delete("/news/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
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