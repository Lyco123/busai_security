# api/ocr.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import time
from models.schemas import OCRResponse, PageResult
from services.ocr_engine import get_ocr_engine
from utils.errors import (
    FileTooLargeError, InvalidPageRangeError, OCRProcessError, OCRTimeoutError,
    PageLimitExceededError, FileCorruptedError, OCRNoTextError, error_to_response
)
from config import config
from utils.logger import logger

router = APIRouter()

def is_image_file(filename: str) -> bool:
    """判断是否为图片文件"""
    return filename.lower().endswith(('.png', '.jpg', '.jpeg'))

def is_pdf_file(filename: str) -> bool:
    """判断是否为 PDF 文件"""
    return filename.lower().endswith('.pdf')

@router.post("/ocr/parse", response_model=OCRResponse)
async def ocr_parse(
    file: UploadFile = File(...),
    language: Optional[str] = Form("ch"),
    page_start: Optional[int] = Form(None),
    page_end: Optional[int] = Form(None),
    mode: Optional[str] = Form("standard")
):
    """
    OCR 解析接口
    """
    if not isinstance(language, str):
        language = config.OCR_LANG
    if not isinstance(mode, str):
        mode = "standard"

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    if language and language != config.OCR_LANG:
        raise HTTPException(
            status_code=400,
            detail=f"当前服务仅支持 language={config.OCR_LANG}"
        )
    if mode and mode != "standard":
        raise HTTPException(
            status_code=400,
            detail="当前服务仅支持 mode=standard"
        )

    start_time = time.time()
    warnings = []
    
    # 1. 检查文件大小
    file_content = await file.read()
    if len(file_content) > config.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413, 
            detail=f"文件超过 {config.MAX_FILE_SIZE_MB}MB 限制"
        )
    
    try:
        # 2. 根据文件类型处理
        if is_pdf_file(file.filename):
            logger.info(f"处理 PDF 文件: {file.filename}")
            ocr_engine = get_ocr_engine()
            
            # PDF OCR 在独立子进程中执行，包含渲染和识别
            ocr_results = await ocr_engine.ocr_pdf(
                file_content,
                page_start=page_start,
                page_end=page_end
            )
             
            # 构建结果
            pages = []
            full_text_parts = []
             
            for page_num, text, confidence in ocr_results:
                pages.append(PageResult(
                    page=page_num,
                    text=text,
                    confidence=confidence
                ))
                full_text_parts.append(text)
                
                if not text:
                    warnings.append(f"第 {page_num} 页未识别到文本")
            
            full_text = "\n".join(full_text_parts)
            
            # 检查是否识别到文本
            if not full_text.strip():
                raise OCRNoTextError()
            
        elif is_image_file(file.filename):
            logger.info(f"处理图片文件: {file.filename}")
            ocr_engine = get_ocr_engine()
            
            # 单张图片 OCR
            text, confidence = await ocr_engine.ocr_image(file_content)
            
            if not text.strip():
                raise OCRNoTextError()
            
            pages = [PageResult(page=1, text=text, confidence=confidence)]
            full_text = text
            
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件格式: {file.filename}"
            )
        
        # 3. 返回成功响应
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return OCRResponse(
            success=True,
            engine="paddleocr",
            full_text=full_text,
            pages=pages,
            elapsed_ms=elapsed_ms,
            warnings=warnings
        )
        
    except HTTPException:
        raise
    except (
        FileTooLargeError, InvalidPageRangeError, OCRProcessError, OCRTimeoutError,
        PageLimitExceededError, FileCorruptedError, OCRNoTextError
    ) as e:
        error_response = error_to_response(e)
        logger.error(f"OCR 失败: {error_response}")
        return OCRResponse(**error_response)
    except Exception as e:
        logger.error(f"未知错误: {str(e)}", exc_info=True)
        return OCRResponse(
            success=False,
            error_code="INTERNAL_ERROR",
            message=f"服务内部错误: {str(e)}"
        )
