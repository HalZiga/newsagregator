from typing import List
from sqlalchemy.orm import Session
from web.model_news import Role as RoleModel, User as UserModel, RoleEnum, NewsStatusEnum, WebNews, TagEnum
from web.schemes import User, UserCreate, UserForModerator, UserUpdate
from web.database import get_db
from web.Guard import create_access_token, get_current_user, role_required
from fastapi import Depends, HTTPException, APIRouter, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=User)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(UserModel).filter(UserModel.login == user.login).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Login already taken")

    roles = db.query(RoleModel).filter(RoleModel.id.in_(user.role_ids)).all()

    user_obj = UserModel(
        login=user.login,
        FIO=user.FIO,
        phone=user.phone,
        email=user.email,
        in_ban=user.in_ban,
        created=datetime.now(timezone.utc),
        roles=roles,
        password = user.password
    )

    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)

    return user_obj

@router.get("/", response_model=List[User])
def get_users(db: Session = Depends(get_db), current_user: UserModel = Depends(role_required(["admin", "moderator"]))):
    if current_user == None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Недостаточно прав для просмотра списка пользователей")
    user_roles = [role.name.value for role in current_user.roles]

    users = db.query(UserModel).all()

    if "admin" in user_roles:
        return users
    elif "moderator" in user_roles:
        return [UserForModerator.model_validate(user) for user in users]
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Недостаточно прав для просмотра списка пользователей")

@router.patch("/{user_id}", response_model=User)
def update_user(user_id: int, user_update: UserUpdate,db: Session = Depends(get_db),
                Current_user: UserModel = Depends(role_required(["admin", "moderator", "author"]))):
    if Current_user == None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="Вы не зашли в систему")
    user_to_update = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user_roles = [role.name.value for role in Current_user.roles]

    if "admin" not in user_roles and Current_user.id != user_id:
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
        new_roles = db.query(RoleModel).filter(RoleModel.id.in_(update_data["role_ids"])).all()
        if not new_roles and update_data["role_ids"]:
            raise HTTPException(status_code=400, detail="Одна или несколько указанных ролей не найдены")
        user_to_update.roles = new_roles
        del update_data["role_ids"]

    print("Тут все")
    db.add(user_to_update)
    db.commit()
    db.refresh(user_to_update)

    return user_to_update

@router.delete("/user/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(role_required(["admin"]))
):
    if current_user == None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="вы не зарегестрированы")
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    db.delete(user)
    db.commit()
    return {}