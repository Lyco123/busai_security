# config.py
import os

class Config:
    # 服务配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    
    # 文件限制
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_MB", 50))
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    MAX_PAGES = int(os.getenv("MAX_PAGES", 100))
    
    # OCR 配置
    OCR_LANG = os.getenv("PADDLEOCR_LANG", "ch")  # ch: 中英文混合
    OCR_USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"
    OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", 60))
    OCR_MAX_CONCURRENCY = int(os.getenv("OCR_MAX_CONCURRENCY", 2))
    OCR_WORKER_BOOT_TIMEOUT_SECONDS = int(
        os.getenv("OCR_WORKER_BOOT_TIMEOUT_SECONDS", 120)
    )
    OCR_PROCESS_TERMINATE_GRACE_SECONDS = float(
        os.getenv("OCR_PROCESS_TERMINATE_GRACE_SECONDS", 2)
    )
    
    # PDF 转换配置
    PDF_DPI = int(os.getenv("PDF_DPI", 200))
    
    # 临时文件目录
    TEMP_DIR = "temp"
    
    # 支持的文件格式
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

config = Config()
