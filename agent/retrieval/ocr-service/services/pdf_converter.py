# services/pdf_converter.py
from typing import Generator, Optional, Tuple

from config import config
from utils.errors import FileCorruptedError, InvalidPageRangeError, PageLimitExceededError
from utils.logger import logger


class PDFConverter:
    @staticmethod
    def verify_runtime_dependencies() -> None:
        import fitz  # noqa: F401

    @staticmethod
    def resolve_page_range(
        total_pages: int,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None
    ) -> Tuple[int, int]:
        start_page = page_start or 1
        end_page = page_end or total_pages

        if start_page < 1 or end_page < 1 or start_page > end_page or end_page > total_pages:
            raise InvalidPageRangeError()

        return start_page, end_page

    @staticmethod
    def iter_page_images(
        pdf_bytes: bytes,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None
    ) -> Generator[Tuple[int, bytes], None, None]:
        """
        Yield rendered PNG bytes for the requested PDF page range.
        """
        try:
            import fitz

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)

            if total_pages > config.MAX_PAGES:
                raise PageLimitExceededError()

            start_page, end_page = PDFConverter.resolve_page_range(
                total_pages,
                page_start=page_start,
                page_end=page_end
            )

            logger.info(f"Rendering PDF pages {start_page}-{end_page} of {total_pages}")

            try:
                for page_num in range(start_page - 1, end_page):
                    page = doc[page_num]
                    pix = page.get_pixmap(dpi=config.PDF_DPI)
                    yield page_num + 1, pix.tobytes("png")
            finally:
                doc.close()
        except (PageLimitExceededError, InvalidPageRangeError):
            raise
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            raise FileCorruptedError(f"PDF conversion failed: {str(e)}")
