from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session as ORMSession
from sqlalchemy.orm import close_all_sessions as sa_close_all_sessions

from clickshare_temperature import orm


def _reset_engine() -> None:
    if orm.engine.EngineBuilder.ENGINE is not None:
        orm.engine.EngineBuilder.ENGINE.dispose()
    orm.engine.EngineBuilder._Session = None
    orm.engine.ENGINE_URI = None
    orm.engine.EngineBuilder.ENGINE = None
    sa_close_all_sessions()


@pytest.fixture(scope="module")
def module_scoped_tmp_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("module_scope")

@pytest.fixture
def uninitialized_db(tmp_path: Path) -> Iterator[None]:
    _reset_engine()
    db_file = tmp_path / "test.db"
    orm.set_engine_uri(f"sqlite:///{db_file}")
    yield
    _reset_engine()



@pytest.fixture
def db_session(uninitialized_db: None) -> Iterator[ORMSession]:
    orm.init_db()
    session = orm.get_session()
    yield session
    session.close()
