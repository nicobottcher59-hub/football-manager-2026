from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from typing import TypeVar


T = TypeVar("T")


def _stable_seed(root_seed: int, namespace: str) -> int:
    """Derive a process-stable 64-bit seed from a match seed + namespace.

    Python's built-in ``hash`` is intentionally salted per process, so it must
    never be used to derive Match Engine RNG streams.  BLAKE2 gives us the same
    derived seed on Windows/Linux, in subprocesses and across calibration jobs.
    """

    if not namespace:
        return root_seed
    payload = f"{root_seed}:{namespace}".encode("utf-8")
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")


class MatchRandom:
    """Deterministic random source for one independently reproducible stream.

    ``MatchRandom(seed)`` keeps the historical root sequence. ``fork(name)``
    creates a deterministic substream whose draws cannot be shifted by draws in
    another subsystem.  This is the Phase 5.10B foundation for clean A/B tests:
    changing passing RNG consumption no longer silently changes shot outcomes.
    """

    def __init__(self, seed: int, *, namespace: str = "") -> None:
        if seed < 0:
            raise ValueError("match random seed must be non-negative")
        if not isinstance(namespace, str):
            raise TypeError("random namespace must be a string")
        self.seed = seed
        self.namespace = namespace
        self._random = random.Random(_stable_seed(seed, namespace))

    def fork(self, namespace: str) -> "MatchRandom":
        if not namespace:
            raise ValueError("random substream namespace cannot be empty")
        child = f"{self.namespace}/{namespace}" if self.namespace else namespace
        return MatchRandom(self.seed, namespace=child)

    def keyed_random(self, *parts: object) -> float:
        """Return a deterministic draw without advancing this stream.

        This is useful for decisions that should be stable for a semantic key
        such as ``(tick, agent_id, purpose)``.  It is deliberately stateless so
        adding unrelated draws elsewhere cannot perturb the result.
        """

        key = ":".join(str(part) for part in parts)
        namespace = f"{self.namespace}/key/{key}" if self.namespace else f"key/{key}"
        return random.Random(_stable_seed(self.seed, namespace)).random()

    def random(self) -> float:
        return self._random.random()

    def uniform(self, minimum: float, maximum: float) -> float:
        return self._random.uniform(minimum, maximum)

    def randint(self, minimum: int, maximum: int) -> int:
        return self._random.randint(minimum, maximum)

    def choice(self, values: Sequence[T]) -> T:
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return self._random.choice(values)
