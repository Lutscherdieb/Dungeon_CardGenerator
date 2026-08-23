"""A single background thread that renders cards one at a time.

Rendering launches Chromium, so it cannot happen inside a request without the
gallery freezing. One worker is deliberate: renders are CPU- and
subprocess-bound, and a second concurrent Chromium buys nothing on one machine.

The status map is in-memory and resets with the process. The durable record is
``CardRow.render_status`` -- this map exists so the UI can distinguish "queued"
from "not started", which the database cannot tell you.
"""

from __future__ import annotations

import queue
import threading
import traceback
from typing import Callable, Dict, Optional

QUEUED = "queued"
RENDERING = "rendering"
DONE = "done"
ERROR = "error"


class RenderQueue:
    def __init__(self) -> None:
        self._q: "queue.Queue[int]" = queue.Queue()
        self._status: Dict[int, str] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._worker: Optional[Callable[[int], None]] = None

    # -- lifecycle ---------------------------------------------------------

    def start(self, worker: Callable[[int], None]) -> None:
        if self._thread is not None:
            return
        self._worker = worker
        self._thread = threading.Thread(target=self._run, name="cardgen-render", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    # -- api ---------------------------------------------------------------

    def enqueue(self, card_id: int) -> None:
        with self._lock:
            self._status[card_id] = QUEUED
        self._q.put(card_id)

    def status(self, card_id: int) -> Optional[str]:
        """In-flight status, or None when this process has not queued the card."""
        with self._lock:
            return self._status.get(card_id)

    def pending(self) -> int:
        return self._q.qsize()

    # -- worker ------------------------------------------------------------

    def _set(self, card_id: int, state: str) -> None:
        with self._lock:
            self._status[card_id] = state

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                card_id = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._set(card_id, RENDERING)
                if self._worker is not None:
                    self._worker(card_id)
                self._set(card_id, DONE)
            except Exception:
                self._set(card_id, ERROR)
                traceback.print_exc()
            finally:
                self._q.task_done()


RENDER_QUEUE = RenderQueue()
