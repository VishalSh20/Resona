"""Admission control (§11) and humanness distribution checks (§12)."""

from __future__ import annotations

import asyncio

import pytest

from voiceeval.domain.enums import Personality
from voiceeval.runtime.caller.humanness import (
    HumannessSample,
    check_humanness,
    distribution,
)
from voiceeval.runtime.caller.persona import PersonaResolver
from voiceeval.runtime.livekit.admission import AdmissionController, AdmissionError


def test_global_concurrency_cap():
    controller = AdmissionController(max_concurrent_calls=2, max_concurrent_per_target=5)
    controller.acquire(attempt_id="a", target_key="t1")
    controller.acquire(attempt_id="b", target_key="t2")
    with pytest.raises(AdmissionError):
        controller.acquire(attempt_id="c", target_key="t3")
    controller.release("a")
    controller.acquire(attempt_id="c", target_key="t3")  # slot freed
    assert controller.in_flight == 2


def test_per_target_concurrency_cap():
    controller = AdmissionController(max_concurrent_calls=10, max_concurrent_per_target=1)
    controller.acquire(attempt_id="a", target_key="target-1")
    with pytest.raises(AdmissionError):
        controller.acquire(attempt_id="b", target_key="target-1")
    controller.acquire(attempt_id="b", target_key="target-2")
    assert controller.in_flight_for_target("target-1") == 1


def test_acquire_is_idempotent_and_release_frees():
    controller = AdmissionController(max_concurrent_calls=1, max_concurrent_per_target=1)
    controller.acquire(attempt_id="a", target_key="t")
    controller.acquire(attempt_id="a", target_key="t")  # no double count
    assert controller.in_flight == 1
    controller.release("a")
    assert controller.in_flight == 0


async def test_soak_never_exceeds_the_cap():
    controller = AdmissionController(max_concurrent_calls=5, max_concurrent_per_target=5)
    peak = 0

    async def worker(attempt_id: str) -> None:
        nonlocal peak
        try:
            controller.acquire(attempt_id=attempt_id, target_key="t")
        except AdmissionError:
            return  # backpressure: the attempt would be requeued
        peak = max(peak, controller.in_flight)
        await asyncio.sleep(0.001)
        controller.release(attempt_id)

    await asyncio.gather(*(worker(f"att_{i}") for i in range(20)))
    assert peak <= 5
    assert controller.in_flight == 0


def test_humanness_within_band_passes():
    persona = PersonaResolver().resolve([Personality.COOPERATIVE])
    samples = [
        HumannessSample(
            response_latency_ms=int(persona.response_latency_ms),
            overlap=False,
            utterance_len=max(1, int(persona.utterance_length * 10)),
            filler=False,
        )
        for _ in range(10)
    ]
    assert check_humanness(samples, persona) == []


def test_humanness_out_of_band_is_flagged():
    persona = PersonaResolver().resolve([Personality.INTERRUPTOR])
    samples = [HumannessSample(response_latency_ms=0, overlap=False, utterance_len=0)]
    violations = check_humanness(samples, persona)
    assert any("overlap_rate" in v for v in violations)


def test_distribution_summary():
    samples = [
        HumannessSample(response_latency_ms=100, overlap=True, utterance_len=4, filler=True),
        HumannessSample(response_latency_ms=300, overlap=False, utterance_len=6, filler=False),
    ]
    summary = distribution(samples)
    assert summary["response_latency_ms"] == 200
    assert summary["overlap_rate"] == 0.5
    assert summary["utterance_len"] == 5
    assert summary["filler_rate"] == 0.5
