"""
Conexão com banco de dados usando SQLAlchemy async.
Suporta PostgreSQL e SQLite (para desenvolvimento).
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Detecta tipo de banco e configura URL
DATABASE_URL = settings.database_url

# Converte URL para async se necessário
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
elif DATABASE_URL.startswith("sqlite://"):
    DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")

# Configuração do engine baseada no tipo de banco
if "sqlite" in DATABASE_URL:
    # SQLite não suporta pool_size
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.debug,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.debug,
        pool_size=5,
        max_overflow=10
    )

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Classe base para todos os models"""
    pass


async def init_db():
    """Inicializa o banco de dados (cria tabelas)"""
    async with engine.begin() as conn:
        # Import models para registrar no metadata
        from app.models import lead, agent, conversation, message
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Fecha conexões com o banco"""
    await engine.dispose()


async def get_db() -> AsyncSession:
    """Dependency para injetar sessão do banco nas rotas"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
