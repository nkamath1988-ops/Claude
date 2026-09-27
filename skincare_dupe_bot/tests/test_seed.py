import importlib
import os
import tempfile

import pytest


@pytest.fixture
def temp_db(monkeypatch):
    """Fresh sqlite file per test, with all db-touching modules reloaded
    against it (db.py binds its engine at import time)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    monkeypatch.setenv("SKINCARE_DB_PATH", path)

    from skincare_dupe_bot import config
    importlib.reload(config)
    from skincare_dupe_bot.database import db
    importlib.reload(db)
    from skincare_dupe_bot.database import seed
    importlib.reload(seed)

    yield seed
    os.remove(path)


def test_seed_loads_all_entries(temp_db):
    kb_count, dupe_count = temp_db.load_seed_data()
    assert kb_count > 0
    assert dupe_count > 0
    assert kb_count == 30


def test_seed_is_idempotent(temp_db):
    first_kb, first_dupe = temp_db.load_seed_data()
    second_kb, second_dupe = temp_db.load_seed_data()

    assert second_kb == 0, "re-running the seed should not create duplicate K-beauty rows"
    assert second_dupe == 0, "re-running the seed should not create duplicate dupe rows"
    assert first_kb > 0 and first_dupe > 0
