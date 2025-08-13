import os
import sys
sys.path.append(os.getcwd())

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from web.model_news import *
from web.database import Base, engine as app_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy import Enum as SQLEnum

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    connectable = app_engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Дополнительные опции для Alembic
            # Эти опции помогают Alembic корректно обрабатывать ENUM-ы при автогенерации
            opts={
                'process_revision_directives': process_revision_directives,
                'include_object': include_object,
            }
        )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

def include_object(object, name, type_, reflected, comparable_values):
    """
    Эта функция вызывается Alembic для каждого объекта в базе данных и в моделях SQLAlchemy.
    Она определяет, должен ли этот объект быть включен в процесс автогенерации миграции.
    Мы используем ее для тонкой настройки того, как Alembic сравнивает ENUMs.
    """
    if type_ == "type" and isinstance(object, SQLEnum) and object.name is not None:
        return object.name.lower() in [e.value.lower() for e in RoleEnum] or \
               object.name.lower() in [e.value.lower() for e in NewsStatusEnum] or \
               object.name.lower() in [e.value.lower() for e in TagEnum]
    return True

def process_revision_directives(context, revision, directives):
    """
    Эта функция позволяет модифицировать директивы миграции перед тем, как они будут записаны в файл.
    Мы используем ее, чтобы Alembic не генерировал операции изменения ENUMs,
    если они уже существуют и не изменились.
    """
    if context.config.cmd_opts.autogenerate:
        for directive in directives:
            for op in directive.upgrade_ops:
                # все операции (add_column, create_table, alter_column и т.д.)
                for element in op.ops:
                    if isinstance(element, (postgresql.ENUM)):
                        element.autogenerate = False

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
