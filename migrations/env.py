import logging
from logging.config import fileConfig
import os

# Set default executor to local for migrations
os.environ.setdefault("MLTF_EXECUTOR", "local")

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")


def get_engine():
    """Get the database engine from Flask app"""
    import sys
    
    # Add src to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    
    from flask import Flask
    from mltf_gateway.server.app import create_app
    
    app = create_app()
    
    with app.app_context():
        from mltf_gateway.server.extensions import db
        return db.engine


def get_target_metadata():
    """Get the target metadata for autogenerate"""
    import sys
    
    # Add src to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    
    from mltf_gateway.server.extensions import db
    return db.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    if not url or url == "driver://user:pass@localhost/dbname":
        # Use environment variable if default value
        url = os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///mltf_gateway.db")
    
    context.configure(
        url=url,
        target_metadata=get_target_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=get_target_metadata(),
            render_as_batch=True  # For SQLite support
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

