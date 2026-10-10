# Continuous voice streaming

Implemented locally on 2026-10-11. Deployment and live call verification remain outstanding.

## Detection and transport

Earshot 1.2.2 is pinned in Core and Bridge. It is a pure Rust neural speech detector, licensed MIT OR Apache-2.0, operating on 256-sample frames at 16 kHz. Each session owns its detector state. It requires no model download or ONNX runtime.

Clients stream microphone audio continuously, including silence. Android sends PCM16 frames of at most 100 ms to Core with `input=stream`. Capture begins only after Core acknowledges `input_mode=stream`; an incompatible server or missing acknowledgment fails the session rather than buffering indefinitely. The handset RMS gates, echo amplitude thresholds, utterance buffer and automatic client Turn messages were removed. Desktop audio cleanup uses pinned Sonora 0.2.0 (BSD-3-Clause), a pure Rust WebRTC audio processor on all platforms, replacing the Windows pass-through and C++ dependency. Echo cancellation, moderate noise suppression and high-pass filtering are enabled. The actual speaker playback is continuously resampled and supplied as the echo reference; capture is processed in 10 ms frames. Platform audio cleanup remains enabled on Android.

Desktop and phone use a shared bounded input admission mechanism with a two-second stall deadline; output remains serviced while input admission waits. Desktop validates the continuous-stream handshake and 100 ms maximum audio frame size. Both use the shared Bridge pipeline, streaming 8 kHz mu-law audio to AssemblyAI. Bridge decodes and interpolates audio to 16 kHz for Earshot without gating provider audio. Earshot endpoints request AssemblyAI ForceEndpoint when a provider turn remains pending; provider final transcripts and semantic backchannel handling remain in use.

The detector uses score 0.5, three consecutive speech frames for onset, ten voiced frames to accept a completed utterance, and 640 ms of silence for an acoustic endpoint. Core keeps 200 ms of preroll and caps an utterance at approximately 30 seconds. Android limits outstanding WebSocket upload data to roughly two seconds. Core validates PCM alignment and streaming frame size.

Android transport is continuous, but its existing Core transcription provider still transcribes each completed utterance as a batch. Bridge transcription is streaming. These paths do not yet have identical provider latency.

## Measurements

VOICE_SPEECH_STARTED and VOICE_AUDIO_ENDPOINT identify Earshot decisions. Core records segment length and speech-to-endpoint duration. Bridge records speech-to-final latency using the last detected speech frame arrival; speech_end_source is earshot_audio_arrival. These timestamps describe server audio arrival, not the physical microphone speech-end time. Android measures response phases from the server endpoint acknowledgment.

## Local verification

- Bridge: 82 existing tests passed; strict Clippy with all targets passed.
- Core: 37 tests passed, 40 database/environment-dependent tests ignored; strict Clippy with all targets and features passed after fixing three existing desktop tool lints. Database migrations were not applied in this task.
- Android: assembleDebug passed.
- Desktop: frontend build passed; 18 frontend tests passed; ESLint completed with zero errors and six existing warnings. Rust check passed with 56 existing unused-code warnings. A fresh debug app bundle was built for the following live test.
- Offline Earshot fixture: fragmented 16 kHz PCM and fragmented 8 kHz mu-law each produced a detected speech start and completed endpoint; silence produced no Core turns.
- Offline Sonora fixture: 1,500 render/capture frames processed without errors; a synthetic echo-only signal had 60.6 dB lower output energy after adaptation. This does not predict real speakerphone performance or isolate echo cancellation from noise suppression.

Offline probes and fixtures are under /tmp. No new repository test files or code comments were added for these audio changes. Previously existing local tests are included in the requested commit of all local changes; stale frontend fixtures/imports were repaired, and the obsolete Pulse default-definition case was removed because that API no longer exists.

The new server behavior has not been directly deployed or live-call verified in this task. A push to main may trigger the configured deployment workflows; their completion must be checked separately before testing. Windows and Linux native builds and real noisy-room/double-talk checks remain unverified on this Mac.

Sources: https://github.com/pykeio/earshot, https://github.com/dignifiedquire/sonora and https://www.assemblyai.com/docs/coding-agent-prompts
