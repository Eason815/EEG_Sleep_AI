import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models.model_manager import ModelManager
from deps import Base, engine, ensure_database_schema
from routers import (
    auth_router,
    analyze_router,
    history_router,
    trends_router,
    regulation_router,
    user_router,
)
from routers.analyze import set_model_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# FastAPI 应用配置
# ============================================================================

app = FastAPI(
    title="睡眠分析 API",
    description="基于脑电的睡眠评估与调控系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 路由挂载
# ============================================================================

app.include_router(auth_router, prefix="/api", tags=["认证"])
app.include_router(analyze_router, prefix="/api", tags=["分析"])
app.include_router(history_router, prefix="/api", tags=["历史"])
app.include_router(trends_router, prefix="/api", tags=["趋势"])
app.include_router(regulation_router, prefix="/api", tags=["调控"])
app.include_router(user_router, prefix="/api", tags=["用户"])

# ============================================================================
# 应用生命周期
# ============================================================================

model_manager: ModelManager = None


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库和模型"""
    global model_manager

    # 初始化数据库
    Base.metadata.create_all(bind=engine)
    ensure_database_schema()

    # 加载模型
    base_dir = Path(__file__).resolve().parent
    try:
        model_manager = ModelManager(data_dir=str(base_dir / "data"), device="cuda")
        model_manager.load_all()
        set_model_manager(model_manager)
        logger.info("Loaded %s model(s)", len(model_manager.models) if model_manager else 0)
    except Exception as exc:
        logger.exception("Failed to initialize model manager: %s", exc)
        model_manager = None


# ============================================================================
# 启动入口
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)