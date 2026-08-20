# models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class PageResult(BaseModel):
    page: int
    text: str
    confidence: float = Field(ge=0, le=1)

class OCRResponse(BaseModel):
    success: bool
    engine: str = "paddleocr"
    full_text: Optional[str] = None
    pages: Optional[List[PageResult]] = None
    elapsed_ms: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    error_code: Optional[str] = None
    message: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
