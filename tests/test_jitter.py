"""Tests for jitter functions."""

from resurge._jitter import full_jitter, random_jitter


def test_full_jitter_range():
    for _ in range(100):
        val = full_jitter(10.0)
        assert 0 <= val <= 10.0


def test_full_jitter_zero():
    assert full_jitter(0) == 0


def test_random_jitter_range():
    for _ in range(100):
        val = random_jitter(5.0)
        assert 5.0 <= val < 6.0


def test_random_jitter_zero():
    val = random_jitter(0)
    assert 0 <= val < 1.0
