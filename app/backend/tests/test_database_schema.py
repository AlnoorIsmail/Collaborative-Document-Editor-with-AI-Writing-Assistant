from sqlalchemy import create_engine, inspect, text

from app.backend.core.database import ensure_runtime_schema


def test_runtime_schema_upgrade_adds_line_spacing_columns_for_existing_sqlite_tables() -> None:
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    content_format VARCHAR(50) NOT NULL,
                    owner_id INTEGER NOT NULL,
                    ai_enabled BOOLEAN NOT NULL,
                    latest_version_id INTEGER,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE document_versions (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    version_number INTEGER NOT NULL,
                    content_snapshot TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    is_restore_version BOOLEAN NOT NULL,
                    created_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO documents
                (id, title, content, content_format, owner_id, ai_enabled, latest_version_id)
                VALUES (1, 'Doc', 'Body', 'rich_text', 1, 1, NULL)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_versions
                (id, document_id, version_number, content_snapshot, created_by, is_restore_version)
                VALUES (1, 1, 1, 'Body', 1, 0)
                """
            )
        )

    ensure_runtime_schema(engine)

    inspector = inspect(engine)
    document_columns = {
        column["name"] for column in inspector.get_columns("documents")
    }
    version_columns = {
        column["name"] for column in inspector.get_columns("document_versions")
    }

    assert "line_spacing" in document_columns
    assert "line_spacing_snapshot" in version_columns
    assert "save_source" in version_columns

    with engine.begin() as connection:
        document_spacing = connection.execute(
            text("SELECT line_spacing FROM documents WHERE id = 1")
        ).scalar_one()
        version_spacing = connection.execute(
            text(
                "SELECT line_spacing_snapshot FROM document_versions WHERE id = 1"
            )
        ).scalar_one()
        version_save_source = connection.execute(
            text("SELECT save_source FROM document_versions WHERE id = 1")
        ).scalar_one()

    assert document_spacing == 1.15
    assert version_spacing == 1.15
    assert version_save_source == "manual"


def test_runtime_schema_upgrade_backfills_restore_versions_with_restore_source() -> None:
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE document_versions (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    version_number INTEGER NOT NULL,
                    content_snapshot TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    is_restore_version BOOLEAN NOT NULL,
                    created_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_versions
                (id, document_id, version_number, content_snapshot, created_by, is_restore_version)
                VALUES (1, 1, 1, 'Body', 1, 1)
                """
            )
        )

    ensure_runtime_schema(engine)

    with engine.begin() as connection:
        version_save_source = connection.execute(
            text("SELECT save_source FROM document_versions WHERE id = 1")
        ).scalar_one()

    assert version_save_source == "restore"


def test_runtime_schema_upgrade_adds_and_backfills_usernames() -> None:
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO users
                (id, email, display_name, password_hash)
                VALUES
                (1, 'owner@example.com', 'Owner Name', 'hash'),
                (2, 'owner2@example.com', 'Owner Name', 'hash')
                """
            )
        )

    ensure_runtime_schema(engine)

    inspector = inspect(engine)
    user_columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    user_indexes = {
        index["name"] for index in inspector.get_indexes("users")
    }

    assert "username" in user_columns
    assert "ix_users_username_unique" in user_indexes

    with engine.begin() as connection:
        usernames = connection.execute(
            text("SELECT username FROM users ORDER BY id")
        ).scalars().all()

    assert usernames == ["owner_name", "owner_name_1"]
