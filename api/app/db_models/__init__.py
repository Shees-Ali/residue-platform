from app.db_models import tables  # noqa: F401  (registers every table on Base.metadata)
from app.db_models.base import Base

__all__ = ["Base"]
