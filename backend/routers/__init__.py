from routers.auth import router as auth_router
from routers.analyze import router as analyze_router
from routers.history import router as history_router
from routers.trends import router as trends_router
from routers.regulation import router as regulation_router
from routers.user import router as user_router

__all__ = [
    "auth_router",
    "analyze_router",
    "history_router",
    "trends_router",
    "regulation_router",
    "user_router",
]