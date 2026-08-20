import unittest
from unittest.mock import patch

from fastapi import HTTPException

from api.ocr import ocr_parse
from utils.errors import InvalidPageRangeError, OCRProcessError, OCRTimeoutError


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


class FakeOCREngine:
    def __init__(self, image_result=("image-text", 0.95), image_error=None, pdf_result=None, pdf_error=None):
        self._image_result = image_result
        self._image_error = image_error
        self._pdf_result = pdf_result or [(2, "page-2", 0.91)]
        self._pdf_error = pdf_error
        self.pdf_calls = []

    async def ocr_image(self, image_bytes: bytes):
        if self._image_error is not None:
            raise self._image_error
        return self._image_result

    async def ocr_pdf(self, pdf_bytes: bytes, page_start=None, page_end=None, timeout_seconds=None):
        self.pdf_calls.append({
            "pdf_bytes": pdf_bytes,
            "page_start": page_start,
            "page_end": page_end,
            "timeout_seconds": timeout_seconds,
        })
        if self._pdf_error is not None:
            raise self._pdf_error
        return self._pdf_result


class OCRApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_unsupported_file_type_returns_http_400(self):
        with self.assertRaises(HTTPException) as ctx:
            await ocr_parse(file=FakeUploadFile("demo.txt", b"hello"))

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_image_timeout_maps_to_ocr_timeout_error_code(self):
        fake_engine = FakeOCREngine(image_error=OCRTimeoutError())

        with patch("api.ocr.get_ocr_engine", return_value=fake_engine):
            response = await ocr_parse(file=FakeUploadFile("demo.png", b"image-bytes"))

        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "OCR_TIMEOUT")

    async def test_unsupported_language_returns_http_400(self):
        with self.assertRaises(HTTPException) as ctx:
            await ocr_parse(
                file=FakeUploadFile("demo.png", b"image-bytes"),
                language="en"
            )

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_unsupported_mode_returns_http_400(self):
        with self.assertRaises(HTTPException) as ctx:
            await ocr_parse(
                file=FakeUploadFile("demo.png", b"image-bytes"),
                mode="fast"
            )

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_pdf_page_range_is_forwarded_and_page_numbers_are_preserved(self):
        fake_engine = FakeOCREngine(pdf_result=[(2, "first", 0.9), (3, "second", 0.8)])

        with patch("api.ocr.get_ocr_engine", return_value=fake_engine):
            response = await ocr_parse(
                file=FakeUploadFile("demo.pdf", b"%PDF"),
                page_start=2,
                page_end=3
            )

        self.assertEqual(fake_engine.pdf_calls, [{
            "pdf_bytes": b"%PDF",
            "page_start": 2,
            "page_end": 3,
            "timeout_seconds": None,
        }])
        self.assertTrue(response.success)
        self.assertEqual([page.page for page in response.pages], [2, 3])

    async def test_invalid_page_range_returns_structured_error(self):
        with patch(
            "api.ocr.get_ocr_engine",
            return_value=FakeOCREngine(pdf_error=InvalidPageRangeError())
        ):
            response = await ocr_parse(
                file=FakeUploadFile("demo.pdf", b"%PDF"),
                page_start=4,
                page_end=2
            )

        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_PAGE_RANGE")

    async def test_pdf_worker_failure_returns_structured_error(self):
        with patch(
            "api.ocr.get_ocr_engine",
            return_value=FakeOCREngine(pdf_error=OCRProcessError())
        ):
            response = await ocr_parse(file=FakeUploadFile("demo.pdf", b"%PDF"))

        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "OCR_PROCESS_ERROR")
