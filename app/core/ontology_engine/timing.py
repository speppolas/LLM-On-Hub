# app/core/ontology_engine/timing.py
import time
from collections import defaultdict

class TimingContext:
    def __init__(self):
        self._start = {}
        self.timings = defaultdict(float)
        self.counts = defaultdict(int)

    def start(self, key: str):
        self._start[key] = time.perf_counter()

    def stop(self, key: str):
        elapsed = (time.perf_counter() - self._start[key]) * 1000  # ms
        self.timings[key] += elapsed
        self.counts[key] += 1

    def summary(self):
        out = {}
        for k, v in self.timings.items():
            out[k] = {
                "total_ms": round(v, 2),
                "count": self.counts[k],
                "mean_ms": round(v / self.counts[k], 2)
            }
        return out
