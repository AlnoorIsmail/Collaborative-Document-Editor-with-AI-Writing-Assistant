from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.backend.core.config import settings
from app.backend.core.usernames import normalize_username_seed


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
)


def ensure_runtime_schema(db_engine) -> None:
    inspector = inspect(db_engine)
    table_names = set(inspector.get_table_names())

    if (
        "users" not in table_names
        and "documents" not in table_names
        and "document_versions" not in table_names
    ):
        return

    with db_engine.begin() as connection:
        if "users" in table_names:
            user_columns = {
                column["name"] for column in inspect(connection).get_columns("users")
            }
            if "username" not in user_columns:
                connection.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN username VARCHAR(64)"
                    )
                )

            existing_rows = connection.execute(
                text(
                    "SELECT id, email, display_name, username FROM users ORDER BY id"
                )
            ).mappings().all()
            used_usernames = {
                str(row["username"]).strip().lower()
                for row in existing_rows
                if row["username"]
            }

            for row in existing_rows:
                current_username = str(row["username"]).strip().lower() if row["username"] else ""
                if current_username:
                    continue

                base_username = normalize_username_seed(
                    str(row["display_name"] or row["email"] or "user")
                )
                candidate = base_username
                suffix = 1
                while candidate.lower() in used_usernames:
                    candidate = f"{base_username}_{suffix}"
                    if len(candidate) > 32:
                        trimmed_base = base_username[: max(1, 32 - len(str(suffix)) - 1)].rstrip("_")
                        candidate = f"{trimmed_base}_{suffix}"
                    suffix += 1

                used_usernames.add(candidate.lower())
                connection.execute(
                    text("UPDATE users SET username = :username WHERE id = :id"),
                    {"username": candidate, "id": row["id"]},
                )

            user_indexes = {
                index["name"] for index in inspect(connection).get_indexes("users")
            }
            if "ix_users_username_unique" not in user_indexes:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username_unique "
                        "ON users (username)"
                    )
                )

        if "documents" in table_names:
            document_columns = {
                column["name"] for column in inspect(connection).get_columns("documents")
            }
            if "line_spacing" not in document_columns:
                connection.execute(
                    text(
                        "ALTER TABLE documents "
                        "ADD COLUMN line_spacing FLOAT NOT NULL DEFAULT 1.15"
                    )
                )
            connection.execute(
                text(
                    "UPDATE documents SET line_spacing = 1.15 "
                    "WHERE line_spacing IS NULL"
                )
            )

        if "document_versions" in table_names:
            version_columns = {
                column["name"]
                for column in inspect(connection).get_columns("document_versions")
            }
            if "line_spacing_snapshot" not in version_columns:
                connection.execute(
                    text(
                        "ALTER TABLE document_versions "
                        "ADD COLUMN line_spacing_snapshot FLOAT NOT NULL DEFAULT 1.15"
                    )
                )
            connection.execute(
                text(
                    "UPDATE document_versions SET line_spacing_snapshot = 1.15 "
                    "WHERE line_spacing_snapshot IS NULL"
                )
            )
            if "save_source" not in version_columns:
                connection.execute(
                    text(
                        "ALTER TABLE document_versions "
                        "ADD COLUMN save_source VARCHAR(20) NOT NULL DEFAULT 'manual'"
                    )
                )
            connection.execute(
                text(
                    "UPDATE document_versions SET save_source = 'manual' "
                    "WHERE save_source IS NULL OR save_source = ''"
                )
            )
            connection.execute(
                text(
                    "UPDATE document_versions SET save_source = 'restore' "
                    "WHERE is_restore_version = 1"
                )
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
