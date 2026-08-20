# utils/errors.py
from typing import Dict

class OCRError(Exception):
    """OCR 服务基础异常"""
    pass

class FileTooLargeError(OCRError):
    pass

class PageLimitExceededError(OCRError):
    pass

class FileCorruptedError(OCRError):
    pass

class OCRTimeoutError(OCRError):
    pass

class OCRProcessError(OCRError):
    pass

class InvalidPageRangeError(OCRError):
    pass

class OCRNoTextError(OCRError):
    pass

def error_to_response(error: Exception) -> Dict:
    """将异常转换为标准错误响应"""
    error_map = {
        FileTooLargeError: ("FILE_TOO_LARGE", f"文件超过 {config.MAX_FILE_SIZE_MB}MB 限制"),
        PageLimitExceededError: ("PAGE_LIMIT_EXCEEDED", f"页数超过 {config.MAX_PAGES} 页限制"),
        FileCorruptedError: ("FILE_CORRUPTED", "文件损坏或无法解析"),
        OCRTimeoutError: ("OCR_TIMEOUT", "OCR 识别超时"),
        OCRProcessError: ("OCR_PROCESS_ERROR", "OCR 子进程异常退出"),
        InvalidPageRangeError: ("INVALID_PAGE_RANGE", "页码范围无效"),
        OCRNoTextError: ("OCR_NO_TEXT", "未识别到任何文本"),
    }
    
    error_code, message = error_map.get(type(error), ("OCR_FAILED", str(error)))
    return {"success": False, "error_code": error_code, "message": message}

# 避免循环导入
from config import config
