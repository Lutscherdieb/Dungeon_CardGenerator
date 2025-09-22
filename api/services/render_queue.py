# api/services/render_queue.py
import threading, queue, time, traceback
from typing import Dict, Optional, Callable

class RenderQueue:
    def __init__(self):
        self.q: "queue.Queue[int]" = queue.Queue()
        self.status: Dict[int, str] = {}   # id -> "queued" | "rendering" | "done" | "error: ..."
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._worker: Optional[Callable[[int], None]] = None

    def start(self, worker: Callable[[int], None]) -> None:
        self._worker = worker
        self._thread = threading.Thread(target=self._run, name="render-worker", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def enqueue(self, card_id: int):
        self.status[card_id] = "queued"
        self.q.put(card_id)

    def _run(self):
        while not self._stop.is_set():
            try:
                card_id = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.status[card_id] = "rendering"
                if self._worker:
                    self._worker(card_id)
                self.status[card_id] = "done"
            except Exception as e:
                self.status[card_id] = f"error: {e}"
                traceback.print_exc()
            finally:
                self.q.task_done()

RENDER_QUEUE = RenderQueue()
