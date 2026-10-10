# Incoming phone call ended during startup

The latest failed incoming call began at 18:58:51 IST on 10 October 2026. The active Railway Bridge deployment was `745148f9-2472-45a0-9e71-97e2e45fb2eb`, status SUCCESS, running commit `d875ec939b44a2c14f8d032ac7e147e1a283c8f3`. The reviewed Bridge checkout matches that commit.

## Observed sequence

| Time (IST) | Event |
| --- | --- |
| 18:58:51.338 | Twilio webhook accepted; signature validation succeeded |
| 18:58:52.098 | Media WebSocket connected |
| 18:58:52.333 | Stream start accepted; greeting response launched |
| 18:58:53.171 | Streaming STT connected after 838 ms |
| 18:58:53.172 | Greeting canceled; session ended after 839 ms |
| 18:58:53.937 | Media stream closed with `protocol error: Twilio audio buffer unavailable` |
| 18:58:54.381 | Twilio status callback reported `completed` |

The session processed 64 incoming frames / 10,240 bytes. It recorded zero partial/final transcripts and zero greeting text chunks, sentences or TTS errors. The canceled greeting's last recorded stage was `core_headers`. That identifies where it was waiting when canceled; it does not demonstrate a Core request failure.

## Failure mechanism

`vox-bridge/src/channels/twilio/stream.rs:160` forwards audio with `input_tx.try_send(...)`. Every send error is converted to `Twilio audio buffer unavailable`, propagated out of the media loop, followed by session shutdown and WebSocket closure.

The input channel has capacity 64 (`src/voice/session/mod.rs:41`). The voice session awaits STT connection before consuming input (`src/voice/session/mod.rs:155`). Audio arriving during this startup interval fills the channel. A burst beyond 64 frames causes `TrySendError::Full`, which the transport currently treats as a fatal protocol error.

Startup queue saturation is the strongly supported cause: the event log shows successful STT connection followed by exactly 64 drained frames and normal session shutdown. The same error text also covers `TrySendError::Closed`, so the logs cannot directly identify which enum variant occurred. There is no preceding STT connection failure or task failure in this call's captured logs. The original error is logged only after cleanup, hiding the instant at which admission failed.

Closing a Twilio Connect/Stream WebSocket ends this call flow. The caller's automatic disconnection follows the Bridge media-handler failure. No greeting audio was recorded before that failure.

## Misleading logs

`VOICE_SESSION_SUMMARY` says `outcome=completed` because the orchestrator receives the cleanup Stop event and exits normally. That describes the task's cleanup, while the enclosing transport failed. Twilio's `completed` status likewise does not mean the AI conversation succeeded.

## Recommended fix

Use bounded backpressure or a separate bounded ingress pump so temporary input saturation does not terminate the call. Preserve explicit handling for a closed voice receiver. Coordinate startup buffering with provider connection latency and avoid solving this solely by increasing channel capacity. Ensure any backpressure design continues servicing output/control frames and has a bounded failure policy for a genuinely stalled provider.

Log input admission failures immediately with Full versus Closed, queue depth/capacity, call/stream IDs and startup state. Propagate transport failure into the final call outcome. Keep credentials, phone numbers and audio contents out of these logs.

Validate with burst input during delayed STT initialization, sustained slow consumption, receiver closure, greeting playback and an actual incoming phone call. The initial log investigation made no production changes. The subsequently authorized fix and deployment are recorded below.

Evidence files retrieved privately: `/tmp/vox-call-cut-0.jsonl` (Bridge), `/tmp/vox-call-cut-1.jsonl` (Core API), and `/tmp/vox-call-cut-deployments.json` (deployment metadata). Raw logs are not attached to this report.

## Fix deployed at 22:11 IST

Bridge now preserves one pending event when the 64-entry input queue is full. While waiting for a queue permit, the transport continues servicing outgoing media and voice-task completion; it pauses reading further incoming frames to apply backpressure. Queue recovery admits the original event without deliberate frame loss. A two-second admission deadline distinguishes a genuinely stalled consumer from transient startup pressure. A closed receiver remains a separate fatal error. Transport failures are logged before cleanup, and the final transport outcome distinguishes failed from completed.

Strict Bridge Clippy and all existing tests passed. An off-repository probe exercised the production admission helper: fill 64 slots, retain the next event, free one slot and re-admit it, then verify a closed receiver fails distinctly. No repository test files or code comments were added.

Railway deployment `3a8c97ca-96c4-466c-8bd4-0ed5751de563` reached SUCCESS. Runtime logs confirm the new container started and filler prewarming completed. Core, Worker and email extraction code were not deployed. The patch remains in the local Bridge working tree; it has not been pushed to GitHub.

A new real incoming phone call has not yet validated the fix. Desktop testing exercises the separate direct Core path and cannot prove Twilio transport behavior.
