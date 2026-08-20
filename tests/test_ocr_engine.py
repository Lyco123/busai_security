import unittest

from services.ocr_engine import OCREngine, WorkerSlot, _WorkerLostError, get_ocr_engine
from utils.errors import InvalidPageRangeError, OCRProcessError, OCRTimeoutError


class FakeProcess:
    def __init__(self, alive=True):
        self.alive = alive

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.alive = False

    def kill(self):
        self.alive = False

    def join(self, timeout=None):
        return None


class FakeConn:
    def __init__(self, poll_result=True, response=None, send_error=None, recv_error=None):
        self.poll_result = poll_result
        self.response = response or {"status": "ok", "result": "done"}
        self.send_error = send_error
        self.recv_error = recv_error
        self.sent_messages = []

    def send(self, value):
        if self.send_error is not None:
            raise self.send_error
        self.sent_messages.append(value)

    def poll(self, timeout=None):
        return self.poll_result

    def recv(self):
        if self.recv_error is not None:
            raise self.recv_error
        return self.response

    def close(self):
        return None


class OCREngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = get_ocr_engine()
        self.engine.shutdown()
        self.engine._initialize()

    def _make_slot(self, worker_id=0, conn=None, process=None):
        return WorkerSlot(
            worker_id=worker_id,
            conn=conn or FakeConn(),
            process=process or FakeProcess(),
        )

    def test_execute_job_on_worker_maps_structured_worker_errors(self):
        slot = self._make_slot(
            conn=FakeConn(response={
                "status": "error",
                "error_type": "InvalidPageRangeError",
                "message": "bad range",
            })
        )

        with self.assertRaises(InvalidPageRangeError):
            self.engine._execute_job_on_worker(slot, {"kind": "pdf"}, timeout_seconds=1)

    def test_execute_job_on_worker_raises_worker_lost_for_dead_process(self):
        slot = self._make_slot(process=FakeProcess(alive=False))

        with self.assertRaises(_WorkerLostError):
            self.engine._execute_job_on_worker(slot, {"kind": "pdf"}, timeout_seconds=1)

    def test_run_job_blocking_replaces_timed_out_worker(self):
        old_slot = self._make_slot(conn=FakeConn(poll_result=False))
        new_slot = self._make_slot(worker_id=0)

        self.engine._started = True
        self.engine._workers = {0: old_slot}
        self.engine._available_workers.put(old_slot)

        def replace_worker(slot):
            self.engine._workers[slot.worker_id] = new_slot
            return new_slot

        self.engine._replace_worker = replace_worker

        with self.assertRaises(OCRTimeoutError):
            self.engine._run_job_blocking({"kind": "image"}, timeout_seconds=0.1)

        recycled = self.engine._available_workers.get_nowait()
        self.assertIs(recycled, new_slot)

    def test_run_job_blocking_replaces_lost_worker_and_raises_process_error(self):
        old_slot = self._make_slot(conn=FakeConn(send_error=BrokenPipeError("broken")))
        new_slot = self._make_slot(worker_id=0)

        self.engine._started = True
        self.engine._workers = {0: old_slot}
        self.engine._available_workers.put(old_slot)

        def replace_worker(slot):
            self.engine._workers[slot.worker_id] = new_slot
            return new_slot

        self.engine._replace_worker = replace_worker

        with self.assertRaises(OCRProcessError):
            self.engine._run_job_blocking({"kind": "image"}, timeout_seconds=0.1)

        recycled = self.engine._available_workers.get_nowait()
        self.assertIs(recycled, new_slot)

    def test_run_job_blocking_reuses_worker_after_structured_error(self):
        slot = self._make_slot(
            conn=FakeConn(response={
                "status": "error",
                "error_type": "InvalidPageRangeError",
                "message": "bad range",
            })
        )

        self.engine._started = True
        self.engine._workers = {0: slot}
        self.engine._available_workers.put(slot)

        with self.assertRaises(InvalidPageRangeError):
            self.engine._run_job_blocking({"kind": "pdf"}, timeout_seconds=0.1)

        recycled = self.engine._available_workers.get_nowait()
        self.assertIs(recycled, slot)
