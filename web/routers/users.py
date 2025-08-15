from typing import List
from sqlalchemy.orm import Session
from web.model_news import User as UserModel
from web.schemes import User, UserCreate, UserForModerator, UserUpdate, UserUpdateBanStatus
from web.database import get_db
from web.Guard import role_required
from fastapi import Depends, APIRouter, status
from dotenv import load_dotenv
from web.services.user_service import (
    create_new_user, get_users_list, get_user_by_id_service, update_user_data,
    update_user_ban_status_service, delete_user_service
)

load_dotenv()

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=User)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    return await  create_new_user(user=user, db=db)

@router.get("/", response_model=List[User])
async def get_users(db: Session = Depends(get_db), current_user: UserModel = Depends(role_required(["admin", "moderator"]))):
    users = await  get_users_list(db=db, current_user=current_user)

    if "moderator" in [role.name.value for role in current_user.roles]:
        return [UserForModerator.model_validate(user) for user in users]
    return users

@router.get("/{user_id}", response_model=User)
async def get_user_by_id(user_id: int, db: Session = Depends(get_db), current_user: UserModel = Depends(role_required(["admin", "moderator", "author", "reader"]))):
    user = await get_user_by_id_service(user_id=user_id, db=db, current_user=current_user)

    if "moderator" in [role.name.value for role in current_user.roles]:
        return UserForModerator.model_validate(user)
    return user


@router.patch("/{user_id}", response_model=User)
async def update_user(
        user_id: int,
        user_update: UserUpdate,
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(role_required(["admin", "moderator", "author", "reader"]))
):
    """
    Обновляет данные пользователя.
    """

    updated_user = await update_user_data(
        user_id=user_id,
        user_update=user_update,
        db=db,
        current_user=current_user
    )
    return User.model_validate(updated_user)

@router.patch("/{user_id}/ban_status", response_model=User)
async def update_user_ban_status(
    user_id: int,
    UserBanStatus: UserUpdateBanStatus,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(role_required(["admin"]))
):
    """
    Заблокировать или разблокировать пользователя по ID.
    Доступно только для администраторов.
    """
    return await update_user_ban_status_service(user_id=user_id, UserBanStatus=UserBanStatus, db=db, current_user=current_user)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(role_required(["admin"]))
):
    await delete_user_service(user_id=user_id, db=db)
    return {}