from __future__ import annotations

import hashlib
import random


class FastMatchRandom:
    """Deterministic RNG root with isolated named substreams.

    Fast simulation deliberately owns its randomness instead of importing the 2D
    engine RNG.  A subsystem can gain or lose random calls without reshuffling
    unrelated outcomes as long as it keeps its namespace stable.
    """

    def __init__(self, seed: int) -> None:
        if seed < 0:
            raise ValueError("fast match seed must be non-negative")
        self.seed = int(seed)
        self._random = random.Random(self.seed)

    def fork(self, namespace: str) -> "FastMatchRandom":
        if not namespace.strip():
            raise ValueError("RNG namespace cannot be empty")
        payload = f"{self.seed}:{namespace}".encode("utf-8")
        digest = hashlib.blake2b(payload, digest_size=8).digest()
        child_seed = int.from_bytes(digest, "big", signed=False)
        return FastMatchRandom(child_seed)

    def random(self) -> float:
        return self._random.random()

    def uniform(self, low: float, high: float) -> float:
        return self._random.uniform(low, high)

    def triangular(self, low: float, high: float, mode: float) -> float:
        return self._random.triangular(low, high, mode)

    def gauss(self, mean: float, sigma: float) -> float:
        return self._random.gauss(mean, sigma)

    def gammavariate(self, alpha: float, beta: float) -> float:
        return self._random.gammavariate(alpha, beta)

    def randint(self, low: int, high: int) -> int:
        return self._random.randint(low, high)

    def choice(self, items):
        return self._random.choice(items)
