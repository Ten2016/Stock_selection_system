"""线程安全的全局速率限制器（在发起 HTTP 请求前调用 acquire）。"""

import threading
import time


class RateLimiter:
    def __init__(self, rate_per_second: float):
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self._min_interval = 1.0 / rate_per_second
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                time.sleep(self._next_allowed - now)
            self._next_allowed = time.monotonic() + self._min_interval
