# services/ocr_engine.py
import asyncio
import multiprocessing
import queue
import threading
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any, Dict, List, Optional, Tuple

from config import config
from services.pdf_converter import PDFConverter
from utils.errors import (
    FileCorruptedError,
    InvalidPageRangeError,
    OCRProcessError,
    OCRTimeoutError,
    PageLimitExceededError,
)
from utils.logger import logger


def _build_paddle_ocr():
    from paddleocr import PaddleOCR

    return PaddleOCR(
        use_angle_cls=True,
        lang=config.OCR_LANG,
        show_log=False,
        use_gpu=config.OCR_USE_GPU,
        enable_mkldnn=True,
    )


def _ocr_single_image_with_engine(ocr: Any, image_bytes: bytes) -> Tuple[str, float]:
    import cv2
    import numpy as np

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return "", 0.0

    result = ocr.ocr(img, cls=True)
    if not result or not result[0]:
        return "", 0.0

    texts = []
    confidences = []
    for line in result[0]:
        texts.append(line[1][0])
        confidences.append(line[1][1])

    return "".join(texts), sum(confidences) / len(confidences)


def _run_image_job(ocr: Any, image_bytes: bytes) -> Tuple[str, float]:
    return _ocr_single_image_with_engine(ocr, image_bytes)


def _run_pdf_job(
    ocr: Any,
    pdf_bytes: bytes,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None
) -> List[Tuple[int, str, float]]:
    page_results = []

    for page_num, image_bytes in PDFConverter.iter_page_images(
        pdf_bytes,
        page_start=page_start,
        page_end=page_end
    ):
        text, confidence = _ocr_single_image_with_engine(ocr, image_bytes)
        page_results.append((page_num, text, confidence))

    return page_results


def _worker_process_main(child_conn: Connection, worker_id: int) -> None:
    try:
        PDFConverter.verify_runtime_dependencies()
        ocr = _build_paddle_ocr()
        child_conn.send({"status": "ready", "worker_id": worker_id})

        while True:
            try:
                job = child_conn.recv()
            except EOFError:
                break

            kind = job.get("kind")
            if kind == "shutdown":
                break

            try:
                if kind == "image":
                    result = _run_image_job(ocr, job["image_bytes"])
                elif kind == "pdf":
                    result = _run_pdf_job(
                        ocr,
                        job["pdf_bytes"],
                        page_start=job.get("page_start"),
                        page_end=job.get("page_end")
                    )
                else:
                    raise OCRProcessError(f"Unsupported OCR job type: {kind}")

                child_conn.send({"status": "ok", "result": result})
            except Exception as exc:
                child_conn.send({
                    "status": "error",
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                })
    except Exception as exc:
        try:
            child_conn.send({
                "status": "boot_error",
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            })
        except Exception:
            pass
    finally:
        child_conn.close()


@dataclass
class WorkerSlot:
    worker_id: int
    process: multiprocessing.Process
    conn: Connection


class _WorkerLostError(OCRProcessError):
    pass


class OCREngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self._ctx = multiprocessing.get_context("spawn")
        self._lock = threading.RLock()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._available_workers: queue.Queue[WorkerSlot] = queue.Queue()
        self._workers: Dict[int, WorkerSlot] = {}
        self._started = False

    def verify_runtime_dependencies(self) -> None:
        logger.info("Verifying OCR runtime dependencies...")
        import cv2  # noqa: F401
        import numpy as np  # noqa: F401
        from paddleocr import PaddleOCR  # noqa: F401

        PDFConverter.verify_runtime_dependencies()
        logger.info("OCR runtime dependencies verified")

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(config.OCR_MAX_CONCURRENCY)
        return self._semaphore

    def _raise_worker_error(self, error_type: str, message: str) -> None:
        error_map = {
            FileCorruptedError.__name__: FileCorruptedError,
            InvalidPageRangeError.__name__: InvalidPageRangeError,
            OCRProcessError.__name__: OCRProcessError,
            PageLimitExceededError.__name__: PageLimitExceededError,
        }

        error_cls = error_map.get(error_type)
        if error_cls is None:
            raise OCRProcessError(message or error_type)
        raise error_cls(message)

    def _terminate_process(self, process: multiprocessing.Process) -> None:
        if not process.is_alive():
            return

        process.terminate()
        process.join(timeout=config.OCR_PROCESS_TERMINATE_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
            process.join(timeout=config.OCR_PROCESS_TERMINATE_GRACE_SECONDS)

    def _close_slot(self, slot: WorkerSlot) -> None:
        try:
            slot.conn.close()
        except Exception:
            pass
        self._terminate_process(slot.process)

    def _spawn_worker(self, worker_id: int) -> WorkerSlot:
        parent_conn, child_conn = self._ctx.Pipe(duplex=True)
        process = self._ctx.Process(
            target=_worker_process_main,
            args=(child_conn, worker_id),
            daemon=True,
        )
        process.start()
        child_conn.close()

        slot = WorkerSlot(worker_id=worker_id, process=process, conn=parent_conn)

        if not parent_conn.poll(config.OCR_WORKER_BOOT_TIMEOUT_SECONDS):
            self._close_slot(slot)
            raise OCRProcessError(f"OCR worker {worker_id} failed to boot in time")

        try:
            response = parent_conn.recv()
        except EOFError as exc:
            self._close_slot(slot)
            raise OCRProcessError(f"OCR worker {worker_id} exited during boot") from exc

        if response.get("status") != "ready":
            self._close_slot(slot)
            raise OCRProcessError(
                response.get("message", f"OCR worker {worker_id} failed to boot")
            )

        logger.info(f"OCR worker {worker_id} started")
        return slot

    def start(self) -> None:
        with self._lock:
            if self._started:
                return

            self._available_workers = queue.Queue()
            self._workers = {}

            try:
                for worker_id in range(config.OCR_MAX_CONCURRENCY):
                    slot = self._spawn_worker(worker_id)
                    self._workers[worker_id] = slot
                    self._available_workers.put(slot)
            except Exception:
                self._shutdown_locked()
                raise

            self._started = True
            logger.info(f"OCR worker pool started with {config.OCR_MAX_CONCURRENCY} workers")

    def _ensure_started(self) -> None:
        if not self._started:
            self.start()

    def _replace_worker(self, slot: WorkerSlot) -> WorkerSlot:
        with self._lock:
            current = self._workers.get(slot.worker_id)
            if current is not None and current is not slot:
                return current

            self._workers.pop(slot.worker_id, None)
            self._close_slot(slot)

            try:
                replacement = self._spawn_worker(slot.worker_id)
            except Exception as exc:
                logger.error(f"Failed to replace OCR worker {slot.worker_id}: {str(exc)}")
                self._shutdown_locked()
                raise OCRProcessError(f"Failed to replace OCR worker {slot.worker_id}") from exc

            self._workers[slot.worker_id] = replacement
            return replacement

    def _release_worker(self, slot: WorkerSlot) -> None:
        with self._lock:
            if not self._started:
                return

            current = self._workers.get(slot.worker_id)
            if current is slot:
                self._available_workers.put(slot)

    def _execute_job_on_worker(self, slot: WorkerSlot, job: Dict[str, Any], timeout_seconds: float) -> Any:
        if not slot.process.is_alive():
            raise _WorkerLostError(f"OCR worker {slot.worker_id} is not running")

        try:
            slot.conn.send(job)
        except (BrokenPipeError, EOFError, OSError) as exc:
            raise _WorkerLostError(f"Failed to dispatch job to worker {slot.worker_id}") from exc

        if not slot.conn.poll(timeout_seconds):
            raise OCRTimeoutError()

        try:
            response = slot.conn.recv()
        except EOFError as exc:
            raise _WorkerLostError(f"Worker {slot.worker_id} closed its pipe unexpectedly") from exc

        if not slot.process.is_alive():
            raise _WorkerLostError(f"Worker {slot.worker_id} exited during job execution")

        if response.get("status") == "ok":
            return response.get("result")

        if response.get("status") == "error":
            self._raise_worker_error(
                response.get("error_type", "OCRProcessError"),
                response.get("message", "")
            )

        raise _WorkerLostError(
            response.get("message", f"Unexpected worker response from {slot.worker_id}")
        )

    def _run_job_blocking(self, job: Dict[str, Any], timeout_seconds: float) -> Any:
        self._ensure_started()
        slot = self._available_workers.get()
        recycle_slot: Optional[WorkerSlot] = slot

        try:
            return self._execute_job_on_worker(slot, job, timeout_seconds)
        except OCRTimeoutError:
            recycle_slot = self._replace_worker(slot)
            raise
        except _WorkerLostError as exc:
            recycle_slot = self._replace_worker(slot)
            raise OCRProcessError(str(exc)) from exc
        finally:
            if recycle_slot is not None:
                self._release_worker(recycle_slot)

    async def _run_job(self, job: Dict[str, Any], timeout_seconds: Optional[float] = None) -> Any:
        timeout = float(timeout_seconds or config.OCR_TIMEOUT_SECONDS)

        async with self._get_semaphore():
            return await asyncio.to_thread(self._run_job_blocking, job, timeout)

    async def ocr_image(self, image_bytes: bytes, timeout_seconds: Optional[float] = None) -> Tuple[str, float]:
        return await self._run_job(
            {"kind": "image", "image_bytes": image_bytes},
            timeout_seconds=timeout_seconds
        )

    async def ocr_pdf(
        self,
        pdf_bytes: bytes,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None,
        timeout_seconds: Optional[float] = None
    ) -> List[Tuple[int, str, float]]:
        return await self._run_job(
            {
                "kind": "pdf",
                "pdf_bytes": pdf_bytes,
                "page_start": page_start,
                "page_end": page_end,
            },
            timeout_seconds=timeout_seconds
        )

    def _shutdown_locked(self) -> None:
        workers = list(self._workers.values())
        self._workers = {}
        self._available_workers = queue.Queue()
        self._started = False

        for slot in workers:
            try:
                if slot.process.is_alive():
                    slot.conn.send({"kind": "shutdown"})
            except Exception:
                pass

        for slot in workers:
            try:
                if slot.process.is_alive():
                    slot.process.join(timeout=config.OCR_PROCESS_TERMINATE_GRACE_SECONDS)
            finally:
                self._close_slot(slot)

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown_locked()
            self._semaphore = None


def get_ocr_engine() -> OCREngine:
    return OCREngine()
