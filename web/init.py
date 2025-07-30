from web.database import SessionLocal, Base, engine
from web.model_news import Role, RoleEnum
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

def create_initial_roles():
    session: Session = SessionLocal()
    try:
        for role_name in RoleEnum:

            existing_role = session.query(Role).filter_by(name = role_name).first()
            if not existing_role:
                new_role = Role(role_name)
                session.add(new_role)
                print(f"Добавляем роль: {role_name}")
            else:
                print(f"Роль уже существует: {role_name}")

        session.commit()
        print("Начальная настройка ролей завершена.")
    except IntegrityError:
        session.rollback()
        print("Произошла ошибка роли, возможно, уже существуют.")
    except Exception as e:
        session.rollback()
        print(f"Произошла ошибка: {e}. Откатываем изменения.")
    finally:
        session.close() # Всегда закрываем сессию

# create_initial_roles()

# def get_roles_from_db():
#     db = SessionLocal()  # создаём сессию
#     try:
#         roles = db.query(Role).all()  # получаем все роли
#         return roles
#     except Exception as e:
#         print("Ошибка при получении ролей из БД:", e)
#         return []
#     finally:
#         db.close()
#
# roles = get_roles_from_db()
# for role in roles:
#     print(f"Role id={role.id}, name={role.name}")