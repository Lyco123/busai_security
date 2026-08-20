# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from api import health, ocr
from services.ocr_engine import get_ocr_engine
from config import config
from utils.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    logger.info("OCR 服务启动中...")
    logger.info(
        f"配置: 最大文件={config.MAX_FILE_SIZE_MB}MB, 最大页数={config.MAX_PAGES}, "
        f"GPU={config.OCR_USE_GPU}, 并发={config.OCR_MAX_CONCURRENCY}, 超时={config.OCR_TIMEOUT_SECONDS}s"
    )
    engine = get_ocr_engine()
    engine.verify_runtime_dependencies()
    engine.start()
    yield
    # 关闭时清理
    logger.info("OCR 服务关闭中...")
    engine.shutdown()

# 创建 FastAPI 应用
app = FastAPI(
    title="OCR Service",
    description="基于 PaddleOCR 的文档识别服务",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 内网环境可配置具体 IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, tags=["Health"])
app.include_router(ocr.router, tags=["OCR"])

@app.get("/")
async def root():
    return {
        "service": "OCR Service",
        "version": "1.0.0",
        "engine": "paddleocr",
        "endpoints": ["/health", "/ocr/parse"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower()
    )
