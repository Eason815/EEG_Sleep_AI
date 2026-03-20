import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from deps import get_current_user, get_db
from entity.response import APIResponse
from entity.user import SleepRecord, User
from utils import serialize_result


logger = logging.getLogger(__name__)

# 全局模型管理器引用，由 main.py 设置
model_manager = None

router = APIRouter()


def set_model_manager(manager):
    """设置模型管理器引用"""
    global model_manager
    model_manager = manager


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "model_loaded": model_manager is not None and model_manager.has_models(),
        "model_count": len(model_manager.models) if model_manager else 0,
        "version": "1.0.0",
    }


@router.get("/models")
async def list_models():
    """列出可用模型"""
    if model_manager is None:
        raise HTTPException(status_code=503, detail="模型管理器尚未初始化")

    return {
        "models": model_manager.list_models(),
        "default_model_id": model_manager.default_model_id,
    }


@router.post("/analyze", response_model=APIResponse)
async def analyze_sleep(
    model_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分析睡眠EDF文件"""
    if not file.filename.endswith(".edf"):
        raise HTTPException(status_code=415, detail="仅支持 EDF 格式文件")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件过大，最大支持 100MB")

    if model_manager is None or not model_manager.has_models():
        raise HTTPException(status_code=503, detail="模型未就绪，请稍后重试")

    try:
        loaded_model = model_manager.get_model(model_id)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"未找到模型: {model_id}")
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        logger.info("开始分析文件 %s | model=%s", file.filename, loaded_model.model_id)
        result = await loaded_model.analyzer.analyze_edf(content, file.filename)

        new_record = SleepRecord(
            user_id=current_user.id,
            filename=file.filename,
            model_family=result.model_family,
            model_name=result.model_name,
            result_json=serialize_result(result),
        )
        db.add(new_record)
        db.commit()

        logger.info("分析完成 | quality_score=%s", result.quality_score)
        return APIResponse(code=200, message="分析成功", data=result)
    except Exception as exc:
        logger.exception("分析失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(exc)}")