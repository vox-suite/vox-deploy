#!/usr/bin/env python3
"""Exercise a complete synthetic dossier and one failed p95 gate."""

import contextlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path

script = Path(__file__).resolve().parents[1] / "scripts/check-single-user-latency.py"
spec = importlib.util.spec_from_file_location("latency_gate", script)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

samples = []
for channel in ("text", "voice"):
    for temperature, count in (("warm", 100), ("cold", 30)):
        for number in range(count):
            sample = {
                "trace_id": f"{channel}-{temperature}-{number}",
                "channel": channel, "temperature": temperature,
                "quality_pass": True, "safety_pass": True,
                "platform_pre_model_ms": 100, "platform_token_relay_ms": 20,
                "model_first_token_ms": 700, "provider_model_ms": 900,
                "full_answer_ms": 1400, "auth_ms": 10, "core_queries_ms": 20,
                "agent_preparation_ms": 40,
            }
            if channel == "text":
                sample["first_text_ms"] = 800
            else:
                sample.update(first_audio_ms=1100, speech_finalization_ms=250,
                              sentence_chunking_ms=50, tts_first_byte_ms=400,
                              playback_start_ms=30)
            samples.append(sample)

run = {
    "metadata": {"concurrency": 1, "cpu": "4 vCPU", "memory_gb": 8,
                 "os": "Linux", "model": "fixed-test-model",
                 "model_provider": "test", "speech_provider": "test"},
    "failures": 0,
    "samples": samples,
    "endpoint_samples": {name: [10] * 100 for name in gate.ENDPOINT_BUDGETS},
}

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "run.json"
    path.write_text(json.dumps(run))
    with contextlib.redirect_stdout(io.StringIO()):
        gate.verify(path)
    run["samples"][0]["platform_pre_model_ms"] = 300
    for sample in run["samples"][:100]:
        sample["platform_pre_model_ms"] = 300
    path.write_text(json.dumps(run))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            gate.verify(path)
    except ValueError as error:
        assert "exceeds" in str(error), error
    else:
        raise AssertionError("over-budget p95 was accepted")

print("single-user latency gate tests passed")
