from sqlalchemy import create_engine, inspect

from app.backend.core.database import Base
from app.backend.models import Document, DocumentPermission, DocumentVersion, Invitation, ShareLink, User


def test_model_metadata_creates_expected_tables() -> None:
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(bind=engine)

    table_names = set(inspect(engine).get_table_names())

    assert User.__tablename__ in table_names
    assert Document.__tablename__ in table_names
    assert DocumentVersion.__tablename__ in table_names
    assert DocumentPermission.__tablename__ in table_names
    assert Invitation.__tablename__ in table_names
    assert ShareLink.__tablename__ in table_names
