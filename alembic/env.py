from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Замените этот блок на импорт вашего асинхронного движка
# Это ваш импорт для Base.metadata
from web.database import DATABASE_URL
from web.model_news import Base  # Импортируем все модели, чтобы Alembic их видел

# Получение объекта config
config = context.config

# Настройте логирование
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Целевая метадата для миграций
target_metadata = Base.metadata


# Прочие значения из alembic.ini
def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    # Создаем синхронный движок для Alembic
    # Это важно для SQLite, так как Alembic работает синхронно
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
