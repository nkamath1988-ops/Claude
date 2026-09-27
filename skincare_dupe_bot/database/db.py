from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from skincare_dupe_bot import config
from skincare_dupe_bot.database.models import Base

_engine = create_engine(config.DATABASE_URL, echo=False)
# expire_on_commit=False: callers routinely read objects (e.g. a dupe's
# kbeauty_product) after their `with get_session()` block has closed and
# committed -- see scheduler.py. Without this, SQLAlchemy expires every
# attribute on commit and the next access raises DetachedInstanceError.
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(_engine)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
