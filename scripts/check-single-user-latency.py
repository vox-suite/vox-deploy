#!/usr/bin/env python3
"""Validate a single-user latency run without conflating provider and platform time."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

TURN_BUDGETS = {
    "platform_pre_model_ms": 250,
    "platform_token_relay_ms": 100,
}
ENDPOINT_BUDGETS = {
    "discovery_ms": 500,
    "task_status_ms": 500,
    "policy_ms": 200,
    "notification_creation_ms": 5000,
}
REPORT_ONLY = (
    "auth_ms", "core_queries_ms", "agent_preparation_ms", "model_first_token_ms",
    "provider_model_ms", "first_text_ms", "full_answer_ms", "speech_finalization_ms",
    "sentence_chunking_ms", "tts_first_byte_ms", "playback_start_ms", "first_audio_ms",
)


def percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * percentage) - 1]


def verify(path: Path) -> None:
    run = json.loads(path.read_text())
    meta = run["metadata"]
    if meta.get("concurrency") != 1:
        raise ValueError("reference run must use one active user and one request in flight")
    for key in ("cpu", "memory_gb", "os", "model", "model_provider", "speech_provider"):
        if not meta.get(key):
            raise ValueError(f"missing reference metadata: {key}")
    if not re.search(r"\b4\s*(?:vCPU|CPU|cores?)\b", str(meta["cpu"]), re.I):
        raise ValueError("reference CPU must be documented as 4 vCPU")
    if meta["memory_gb"] != 8 or "linux" not in str(meta["os"]).lower():
        raise ValueError("reference machine must be 4 vCPU, 8 GB Linux")
    if run.get("failures") != 0:
        raise ValueError("latency run must record zero failed turns")
    samples = run["samples"]
    for channel in ("text", "voice"):
        for temperature, count in (("warm", 100), ("cold", 30)):
            matching = [s for s in samples if s.get("channel") == channel and s.get("temperature") == temperature]
            if len(matching) < count:
                raise ValueError(f"{channel}/{temperature} has {len(matching)} turns; needs {count}")
            if any(not s.get("quality_pass") or not s.get("safety_pass") for s in matching):
                raise ValueError(f"{channel}/{temperature} includes an answer-quality or safety failure")
            if any(not s.get("trace_id") for s in matching):
                raise ValueError(f"{channel}/{temperature} lacks correlated trace IDs")
            print(f"{channel}/{temperature}: {len(matching)} turns")
            for metric in (*TURN_BUDGETS, *REPORT_ONLY):
                values = [s[metric] for s in matching if metric in s]
                if not values:
                    continue
                if len(values) != len(matching):
                    raise ValueError(f"{channel}/{temperature} has incomplete {metric} measurements")
                if any(not isinstance(value, (int, float)) or isinstance(value, bool)
                       or value < 0 or not math.isfinite(value) for value in values):
                    raise ValueError(f"{channel}/{temperature} has invalid {metric} measurements")
                p50, p95 = percentile(values, 0.50), percentile(values, 0.95)
                print(f"  {metric}: p50={p50:.1f} ms p95={p95:.1f} ms")
                if temperature == "warm" and metric in TURN_BUDGETS and p95 > TURN_BUDGETS[metric]:
                    raise ValueError(f"{channel} {metric} p95 {p95:.1f} ms exceeds {TURN_BUDGETS[metric]} ms")
            required = (
                "platform_pre_model_ms", "platform_token_relay_ms", "model_first_token_ms",
                "provider_model_ms", "full_answer_ms", "auth_ms", "core_queries_ms",
                "agent_preparation_ms",
            )
            required += ("first_text_ms",) if channel == "text" else (
                "first_audio_ms", "speech_finalization_ms", "sentence_chunking_ms",
                "tts_first_byte_ms", "playback_start_ms",
            )
            if any(any(metric not in sample for metric in required) for sample in matching):
                raise ValueError(f"{channel}/{temperature} lacks a required turn-level timing")
            for metric in required:
                if any(not isinstance(s[metric], (int, float)) or isinstance(s[metric], bool)
                       or s[metric] < 0 or not math.isfinite(s[metric]) for s in matching):
                    raise ValueError(f"{channel}/{temperature} has invalid {metric} measurements")
    endpoint_samples = run.get("endpoint_samples", {})
    for metric, budget in ENDPOINT_BUDGETS.items():
        values = endpoint_samples.get(metric, [])
        if len(values) < 100 or any(not isinstance(value, (int, float)) or value < 0 or not math.isfinite(value) for value in values):
            raise ValueError(f"{metric} needs at least 100 valid independent measurements")
        p50, p95 = percentile(values, 0.50), percentile(values, 0.95)
        print(f"{metric}: p50={p50:.1f} ms p95={p95:.1f} ms")
        if p95 > budget:
            raise ValueError(f"{metric} p95 {p95:.1f} ms exceeds {budget} ms")
    print("Single-user latency evidence passes; full provider timings remain visible above.")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: check-single-user-latency.py RUN.json")
        verify(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"latency gate blocked: {error}", file=sys.stderr)
        sys.exit(1)
