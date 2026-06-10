from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    """Create all tables (for dev/testing). Use alembic in production."""
    async with engine.begin() as conn:
        from app.models import User, Subscription, Payment, Tariff, Server, Referral  # noqa
        await conn.run_sync(Base.metadata.create_all)
