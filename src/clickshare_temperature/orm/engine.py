from __future__ import annotations
import threading
from typing import ClassVar, Protocol
# import contextvars

from sqlalchemy import (
    Engine,
    URL as SQLAlchemyURL,
    make_url,
    create_engine as sa_create_engine,
    event,
)
from sqlalchemy.orm import (
    sessionmaker,
    Session as ORMSession,
)

from .base import Base

# session_context: contextvars.ContextVar[ORMSession] = contextvars.ContextVar("orm_session")


class EngineBuilderProto(Protocol):
    def __call__(self) -> Engine: ...



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
    return sa_create_engine(uri, echo=False)#, pool_size=10, max_overflow=20, pool_timeout=60)



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

    # @classmethod
    # def get_engine(cls) -> Engine:
    #     return get_engine()

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
def set_sqlite_pragma(dbapi_connection, connection_record):
    # the sqlite3 driver will not set PRAGMA foreign_keys
    # if autocommit=False; set to True temporarily
    ac = dbapi_connection.autocommit
    dbapi_connection.autocommit = True

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

    # restore previous autocommit setting
    dbapi_connection.autocommit = ac
