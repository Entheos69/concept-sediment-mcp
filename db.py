"""
Concept Sediment MCP — Database Connection

Conexión a PostgreSQL + pgvector via SQLAlchemy.
Stateless: cada request crea y cierra su propia sesión.
"""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# ── Configuración ──
_engine = None
_SessionLocal = None


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise ValueError(
            "DATABASE_URL not set. Example: "
            "postgresql://user:pass@host:port/concept_sediment"
        )
    # SQLAlchemy necesita 'postgresql://' no 'postgres://'
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def get_engine():
    """Obtiene o crea el engine singleton."""
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(
            _get_database_url(),
            pool_size=5,
            max_overflow=10,
            pool_recycle=600,
            pool_pre_ping=True,
            echo=False,
        )
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    """Crea una sesión nueva. Caller es responsable de cerrarla."""
    get_engine()  # asegurar engine existe
    return _SessionLocal()


def dispose_engine():
    """Cierra el engine y limpia el pool."""
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
        _engine = None
        _SessionLocal = None


def test_connection() -> bool:
    """Verifica la conexión a la DB."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"DB connection failed: {e}")
        return False
