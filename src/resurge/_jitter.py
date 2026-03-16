"""Jitter functions for retry backoff."""

from __future__ import annotations

import random


def full_jitter(value: float) -> float:
    """AWS-style full jitter: uniform random in [0, value]."""
    return random.uniform(0, value)


def random_jitter(value: float) -> float:
    """Add up to 1 second of random jitter."""
    return value + random.random()
