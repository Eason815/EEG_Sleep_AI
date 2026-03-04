from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from models.response import APIResponse, AnalysisResult, SleepStats
from models.user import User, SleepRecord
from services.analyzer import SleepAnalyzer
from train import SleepStageNetV8
from pathlib import Path
import logging
from database import engine, SessionLocal, Base, get_db
from auth import get_password_hash, verify_password, create_access_token, decode_access_token
from fastapi import Depends, Header, Form
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效或过期的token")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="睡眠分析 API",
    description="基于深度学习的睡眠分期与质量评估系统",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
analyzer: SleepAnalyzer = None

@app.on_event("startup")
async def startup_event():
    global analyzer
    
    # 初始化数据库表
    Base.metadata.create_all(bind=engine)
    
    # 确保路径是相对于 main.py 的正确位置
    BASE_DIR = Path(__file__).resolve().parent
    MODEL_PATH = str(BASE_DIR / "data" / "model021101.pth")

    try:
        # 直接实例化
        from train import SleepStageNetV8
        analyzer = SleepAnalyzer(
            model_class=SleepStageNetV8,
            model_path=MODEL_PATH,
            device='cuda'
        )
        print("✅ 模型初始化并加载成功")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        # 打印完整堆栈
        import traceback
        traceback.print_exc()



@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "model_loaded": analyzer is not None,
        "version": "1.0.0"
    }


@app.post("/api/analyze", response_model=APIResponse)
async def analyze_sleep(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    睡眠分析接口
    
    参数:
        file: EDF格式的睡眠数据文件
    
    返回:
        分析结果（包含睡眠阶梯图、统计数据、质量评分等）
    """
    # 1. 验证文件
    if not file.filename.endswith('.edf'):
        raise HTTPException(
            status_code=415,
            detail="仅支持 EDF 格式文件"
        )
    
    # 2. 检查文件大小（限制100MB）
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="文件过大，最大支持 100MB"
        )
    
    # 3. 检查模型状态
    if analyzer is None:
        raise HTTPException(
            status_code=503,
            detail="模型未就绪，请稍后重试"
        )
    
    try:
        # 4. 执行分析
        logger.info(f"开始分析文件: {file.filename}")
        result = await analyzer.analyze_edf(content, file.filename)
        
        # 存入数据库
        new_record = SleepRecord(
            user_id=current_user.id,
            filename=file.filename,
            result_json=result.json()
        )
        db.add(new_record)
        db.commit()
        
        logger.info(f"✅ 分析完成，质量分数: {result.quality_score}")
        
        return APIResponse(
            code=200,
            message="分析成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"❌ 分析失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"分析失败: {str(e)}"
        )


@app.post("/api/analyze/mock", response_model=APIResponse)
async def analyze_mock(file: UploadFile = File(...)):
    """
    模拟接口（用于前端开发测试）
    """
    import random
    import numpy as np
    
    # 生成8小时模拟数据
    total_epochs = 960
    hypnogram = []
    
    for i in range(total_epochs):
        if i < 20:
            hypnogram.append(0)  # 清醒
        elif i < 60:
            hypnogram.append(2)  # 入睡
        elif i < 200:
            hypnogram.append(random.choice([2, 3, 3, 3]))
        elif i < 350:
            hypnogram.append(random.choice([1, 1, 2]))
        else:
            hypnogram.append(random.choice([1, 1, 2, 2, 3]))
    
    stats = {
        "W_ratio": hypnogram.count(0) / total_epochs,
        "REM_ratio": hypnogram.count(1) / total_epochs,
        "Light_ratio": hypnogram.count(2) / total_epochs,
        "Deep_ratio": hypnogram.count(3) / total_epochs
    }
    
    return APIResponse(
        code=200,
        message="模拟分析成功",
        data=AnalysisResult(
            hypnogram=hypnogram,
            stats=SleepStats(**stats),
            quality_score=random.randint(70, 95),
            total_epochs=total_epochs,
            duration_hours=8.0,
            sleep_efficiency=random.uniform(80, 95),
            sleep_latency=random.randint(5, 30),
            waso=random.randint(10, 50),
            rem_latency=random.randint(70, 120)
        )
    )


@app.post("/api/register")
async def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    new_user = User(username=username, password_hash=get_password_hash(password))
    db.add(new_user)
    db.commit()
    return {"message": "注册成功"}

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/history")
async def get_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).all()
    return records

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
