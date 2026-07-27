from __future__ import annotations

import threading
import warnings
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Literal,
    NotRequired,
    Protocol,
    TypedDict,
    Unpack,
)

from sqlalchemy import (
    URL as SQLAlchemyURL,
)
from sqlalchemy import (
    Engine,
    event,
    make_url,
)
from sqlalchemy import (
    create_engine as sa_create_engine,
)
from sqlalchemy.orm import (
    Session as ORMSession,
)
from sqlalchemy.orm import (
    sessionmaker,
)

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool.base import ConnectionPoolEntry

from .base import Base


class EngineBuilderProto(Protocol):
    def __call__(self) -> Engine: ...



type SqliteJournalMode = Literal["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"]
"""Type representing the possible values for the SQLite journal_mode PRAGMA"""


class SqlitePragmaDict(TypedDict):
    """A TypedDict representing common SQLite PRAGMA settings
    """
    foreign_keys: NotRequired[Literal["ON", "OFF"]]
    """Whether foreign key constraints are enforced (ON) or not (OFF)

    Default is "ON" to enforce foreign key constraints.
    """

    journal_mode: NotRequired[SqliteJournalMode]
    """The journal mode used by SQLite for transactions

    Default is "WAL" (Write-Ahead Logging) for better concurrency and performance.
    """

    cache_size: NotRequired[str]
    """The number of pages to use for the SQLite page cache (negative values indicate size in KB)

    Default is "-64000" to use 64 MB of cache.
    """

    synchronous: NotRequired[Literal["OFF", "NORMAL", "FULL", "EXTRA"]]
    """The synchronous mode used by SQLite for transactions

    Default is "NORMAL" for a balance between performance and durability.
    """

    busy_timeout: NotRequired[str]
    """The busy timeout in milliseconds for SQLite when a database is locked

    Default is "5000" (5 seconds) to wait for a lock before raising an error.
    """

    temp_store: NotRequired[Literal["DEFAULT", "FILE", "MEMORY"]]
    """The location where temporary tables and indices are stored

    Default is "MEMORY" to store temporary tables and indices in memory.
    """


_SQLITE_PRAGMAS: SqlitePragmaDict = {
    "foreign_keys": "ON",
    "journal_mode": "WAL",
    "cache_size": "-64000",
    "synchronous": "NORMAL",
    "busy_timeout": "5000",
    "temp_store": "MEMORY",
}

def get_sqlite_pragmas() -> SqlitePragmaDict:
    """Get the SQLite PRAGMA settings used by the application"""
    return _SQLITE_PRAGMAS.copy()


def set_sqlite_pragmas(**pragmas: Unpack[SqlitePragmaDict]) -> None:
    """Set the :class:`Sqlite Pragma settings <SqlitePragmaDict>` for the application

    Any pragmas not specified will remain at their current values.
    The default values are shown in the :class:`SqlitePragmaDict` definition.

    .. important::

        This function should be called before any database operations are performed.
    """
    if EngineBuilder.ENGINE is not None:
        warnings.warn(
            "SQLite PRAGMA settings should be set before the engine is created. "
            "Changing PRAGMA settings after the engine is created may not have any effect.",
            stacklevel=2
        )
    _SQLITE_PRAGMAS.update(pragmas)


def create_engine_uri(
    scheme: str = 'sqlite',
    path: str = 'db.sqlite3',
    kwargs: dict[str, str] | None = None
) -> SQLAlchemyURL:
    """Create a SQLAlchemy database URI from the given parameters
    """
    return SQLAlchemyURL.create(
        drivername=scheme,
        database=path,
        query=kwargs or {},
    )


ENGINE_URI: SQLAlchemyURL | None = None
_ENGINE_URI_LOCK: threading.Lock = threading.Lock()


def set_engine_uri(uri: str|SQLAlchemyURL) -> None:
    """Set the global engine URI for the application

    This should be called before any database operations are performed.

    .. note::

        This function protected by an internal lock to ensure thread safety.

    """
    global ENGINE_URI
    if not isinstance(uri, SQLAlchemyURL):
        uri = make_url(uri)
    with _ENGINE_URI_LOCK:
        if ENGINE_URI is not None and ENGINE_URI != uri:
            raise ValueError(
                f"Engine URI has already been set to '{ENGINE_URI}', "
                f"cannot change to '{uri}'"
            )
        ENGINE_URI = uri


def get_engine_uri() -> SQLAlchemyURL:
    """Get the global engine URI for the application

    If the engine URI has not been set yet, it will be created with default
    parameters.

    .. note::

        This function protected by an internal lock to ensure thread safety.
    """
    global ENGINE_URI
    with _ENGINE_URI_LOCK:
        if ENGINE_URI is None:
            ENGINE_URI = create_engine_uri()
        return ENGINE_URI



def _create_default_engine() -> Engine:
    uri = get_engine_uri()
    return sa_create_engine(uri, echo=False)



class EngineBuilder:
    """Class responsible for building and providing access to the SQLAlchemy Engine and Session
    """
    builder_func: ClassVar[EngineBuilderProto] = _create_default_engine
    """Callable to build the SQLAlchemy Engine"""
    ENGINE: ClassVar[Engine | None] = None
    """The SQLAlchemy Engine instance"""
    _Session: ClassVar[sessionmaker[ORMSession] | None] = None
    """The SQLAlchemy Session factory"""

    @classmethod
    def set_builder(cls, func: EngineBuilderProto) -> None:
        """Set a custom :attr:`builder_func` to build the SQLAlchemy Engine

        This allows for customizing the Engine creation, e.g. to set specific
        connection parameters or use a different database backend.
        """
        if cls.ENGINE is not None:
            raise RuntimeError("Engine already created; cannot change builder function.")
        cls.builder_func = func

    @classmethod
    def build_engine(cls) -> Engine:
        """Build the SQLAlchemy Engine using the :attr:`builder_func`
        """
        return cls.builder_func()


    @classmethod
    def create_engine(cls) -> Engine:
        """Create the SQLAlchemy Engine if it does not already exist, and return it
        """
        if cls.ENGINE is None:
            assert cls._Session is None
            cls.ENGINE = cls.build_engine()
            cls._Session = sessionmaker(bind=cls.ENGINE)
        return cls.ENGINE

    @classmethod
    def Session(cls) -> ORMSession:
        """Get a new SQLAlchemy Session
        """
        if cls._Session is None:
            cls.create_engine()
        assert cls._Session is not None
        return cls._Session()


def create_engine() -> Engine:
    """Create the SQLAlchemy Engine

    This is a shortcut function for :meth:`EngineBuilder.create_engine`.
    """
    return EngineBuilder.create_engine()

def init_db() -> None:
    """Initialize the database by creating all tables
    """
    engine = create_engine()
    Base.metadata.create_all(bind=engine)

def get_session() -> ORMSession:
    """Get a new SQLAlchemy Session

    This is a shortcut function for :meth:`EngineBuilder.Session`.
    """
    return EngineBuilder.Session()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(
    dbapi_connection: DBAPIConnection,
    connection_record: ConnectionPoolEntry
) -> None:
    # the sqlite3 driver will not set PRAGMA foreign_keys
    # if autocommit=False; set to True temporarily
    ac = dbapi_connection.autocommit
    dbapi_connection.autocommit = True

    cursor = dbapi_connection.cursor()
    for pragma, value in get_sqlite_pragmas().items():
        cursor.execute(f"PRAGMA {pragma}={value}")
    cursor.close()

    # restore previous autocommit setting
    dbapi_connection.autocommit = ac
