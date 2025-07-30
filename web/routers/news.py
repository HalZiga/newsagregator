from sqlalchemy.orm import Session
from web.model_news import  User as UserModel, NewsStatusEnum, WebNews, TagEnum, RoleEnum
from web.database import get_db
from web.schemes import News, NewsCreate, NewsUpdate
from web.Guard import get_current_user, role_required
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

router = APIRouter(prefix="/news", tags=["news"])

@router.post("/", response_model=News, status_code=status.HTTP_201_CREATED)
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

@router.get("/published", response_model=List[News])
async def get_published_news(
    db: Session = Depends(get_db)
):
    """
    Получить список всех опубликованных новостей. Доступно всем без авторизации.
    """
    # Просто фильтруем по статусу "Опубликовано"
    published_news = db.query(WebNews).filter(WebNews.status == NewsStatusEnum.Published).order_by(WebNews.published_at.desc()).all()
    return published_news

@router.get("/", response_model=List[News])
async def get_all_news_authorized(
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_current_user)
):
    """
    Получить список всех новостей.
    Опубликованные новости доступны всем.
    Черновики и архивы доступны только админам, модераторам и автору черновика.
    """
    user_roles_names = [role.name.value for role in current_user.roles]

    news_query = db.query(WebNews)

    if RoleEnum.Admin.value in user_roles_names or RoleEnum.Moderator.value in user_roles_names:
        pass
    else:
        news_query = news_query.filter(WebNews.status == NewsStatusEnum.Published)

        if RoleEnum.Author.value in user_roles_names:
            news_query = news_query.union(
                db.query(WebNews).filter(
                    WebNews.created_by_user_id == current_user.id
                )
            )

    return news_query.order_by(WebNews.published_at.desc()).all()


@router.get("/{news_id}", response_model=News)
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

    if news.status != NewsStatusEnum.Published:
        if not current_user or (
            "admin" not in user_roles and
            "moderator" not in user_roles and
            current_user.id != news.author_id
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этой новости")
    news.views += 1
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


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
    is_author_of_this_news = current_user.id == news.created_by_user_id

    if not is_admin and not is_author_of_this_news:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У вас нет прав на редактирование этой новости.")

    update_data = news_data.model_dump(exclude_unset=True) #только те поля, которые были переданы


    if update_data["status"] == NewsStatusEnum.Published and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только модератор могут публиковать новости.")

    for key, value in update_data.items():
        setattr(news, key, value)
    news.redacted_at = datetime.now(timezone.utc)
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


@router.patch("/{news_id}/publish", response_model=News)
async def publish_news(
        news_id: int,
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(role_required(["moderator"]))
):
    """
    Опубликовать новость. Доступно только модераторам.
    """
    news = db.query(WebNews).filter(WebNews.id == news_id).first()
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")

    if news.status == NewsStatusEnum.Published:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Новость уже опубликована.")

    news.status = NewsStatusEnum.Published

    if not news.published_at:
        news.published_at = datetime.now(timezone.utc)

    news.published = datetime.now(timezone.utc)
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