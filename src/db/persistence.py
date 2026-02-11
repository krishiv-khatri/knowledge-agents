from contextlib import contextmanager
from sqlalchemy import create_engine, Select, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, Query, joinedload

from db.models import Base

class DbManager:
    
    def __init__(self, dialect: str, sync_driver: str, async_driver: str, host: str, port: int, db: str, user: str, password: str, debug: bool = False) -> None:
        # Create an in-memory SQLite database
        url = f"{dialect}+{sync_driver}://{user}:{password}@{host}:{port}/{db}?sslmode=require"
        #print(url)
        self._url = url
        self._engine = create_engine(url, echo=debug)
        self.__create_table()
        async_url = f"{dialect}+{async_driver}://{user}:{password}@{host}:{port}/{db}?ssl=require"

        self._async_url = async_url
        self._async_engine = create_async_engine(async_url, echo=debug)
        self._raw_uri = f"{dialect}://{user}:{password}@{host}:{port}/{db}"

        # 
        self._async_engine.dialect.supports_sane_rowcount = False
        # async_sessionmaker: a factory for new AsyncSession objects.
        # expire_on_commit - don't expire objects after transaction commit
        self._async_session_maker = async_sessionmaker(self._async_engine, expire_on_commit=False)

    def __create_table(self):
        #Base.metadata.drop_all(self._engine)
        Base.metadata.create_all(self._engine)

    def engine(self):
        return self._engine
        
    # @contextmanager
    # def session(self) -> Session:
    #     with Session(self._engine) as session:
    #         yield session

    async def save_async(self, obj: Base):
        with Session(self._engine) as session:
            # slow merge operation, use INSERT ON UPDATE better
            # session.scalar(stmt)
            session.merge(obj)
            session.commit()
