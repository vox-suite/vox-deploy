# Voice latency review — 10 October 2026

Status: desktop server-audio flow exercised after unlock; two instrumented greetings measured. Phone startup queue fix deployed to Bridge. A representative latency distribution and controlled long-conversation validation remain unavailable. The new Core instrumentation has not been deployed.

## Evidence and coverage

Reviewed the desktop audio engine, voice client, local ASR/TTS path, Core native voice socket, AssemblyAI batch client, and Bridge voice/transport metrics. Desktop uses Core `/v1/me/voice/socket` directly. Bridge/Twilio measurements describe a different pipeline and must not be combined with desktop measurements.

The desktop currently attempts local ASR/TTS initialization before opening its socket. If initialization succeeds, Core supplies agent text and desktop synthesizes speech; otherwise Core performs STT and TTS. Each new session now logs which route it selected. The previous server email-extraction changes remain separate from this voice work.

Production Railway queries used the resolved Vox production environment and explicit Core API and Bridge service IDs. A bounded query of the latest successful deployment for each service, filtered to `VOICE_`, over the preceding two days returned zero matching lines. This does not establish that there were no calls: deployment selection, retention and configured log levels limit coverage.

Native computer control initially reported the Mac locked. After unlock, Vox was restarted from the rebuilt bundle and a desktop voice session was exercised. Logs confirm microphone submission, server transcripts, generated audio, and PCM output callbacks. Audio was not independently listened to or recorded, and response correctness was not verified. No lock bypass was attempted.

| Requested measurement | Observed samples | Result |
| --- | ---: | --- |
| Greeting to PCM output callback | 2 instrumented | 1,101.23–1,344.867 ms; not a controlled cold/warm cohort |
| User turn timing | 0 accepted | Observed raw intervals excluded due to overlapping unresolved utterances |
| Speech-end proxy to first PCM playback | 0 accepted | Correlation ambiguity prevents reliable user-turn attribution |
| Long-conversation drift | 0 | Pending desktop test |
| Barge-in acknowledgment and stop behavior | 0 | Pending desktop test |
| Median / tail latency | 0 | Unavailable |

## Existing measurements that work

Core already records context preparation, greeting setup, agent stream opening, first text delta, sentence-level TTS connection/first-chunk/total duration, audio enqueue, output queue/write duration, first WebSocket audio send and turn lifecycle. These provide useful server-side attribution when emitted by the running deployment.

Bridge has separate response milestones, streaming STT finalization, TTS sentence timings, transport queue/write metrics, and Twilio playback-mark acknowledgment. A mark invalidated by interruption is differentiated from a normal playback mark. These are useful telephony metrics, but acknowledgment of a playback mark is not a measurement of first audible desktop output.

The desktop had socket and audio-engine startup duration, transcript/first text/first received binary frame timing, MP3 decoding, frame gaps, playback queue depth, mic quality, and underrun counters. Its first-audio measurement ended at frame receipt. Its “done” measurement ended at response generation, while queued speech could continue playing.

## Changes implemented

### Desktop

Structured `VOICE_LATENCY` JSON events identify the client session and, when available, server turn. The server connection event maps the client session to the server session ID. New metadata is optional in desktop deserialization, preserving compatibility with the currently deployed server. Android ignores unknown server fields.

Added route setup, socket opening, utterance endpointing, dispatch, transcript, first text, first received audio, first PCM output callback, generation completion, interrupt request/acknowledgment, application ping RTT, error and session-end events. The PCM event includes the speech-end proxy and receipt-to-render delay where available.

The audio callback records the first queued PCM boundary through atomics; it performs no new logging or file I/O. Logging happens outside the callback. Queue position accounts for previously buffered audio. Polling the recorded timestamp does not add the polling interval to the reported duration.

Removed transcript contents from the touched diagnostic logs, retaining character counts. Reset inter-frame timing for each utterance, avoid labeling a later turn as a greeting, ignore stale `done` messages, and drop binary audio without an active response turn.

Local TTS logs queue wait, synthesis duration, generated audio duration and stale playback epoch. This path synthesizes a complete sentence before enqueueing PCM; its queue/synthesis measurements are separate from server TTS. Playback epochs alone do not uniquely identify every local sentence across uninterrupted turns.

### Core

The connection message now exposes a server session ID. Thinking messages identify greeting versus user turn. Successful text-only responses are recorded as `text_only_completed`, avoiding a false `no_answer_audio` result when desktop owns TTS.

Queued audio carries its cancellation token and is discarded before writing when canceled. Cancellation also stops waiting for batch STT and suppresses a canceled transcript. Audio already written to the network cannot be retracted by this check.

AssemblyAI now logs upload duration, job-creation duration, polling duration, poll count, scheduled polling sleep and total completion duration at info level. Provider stage logs inherit the native turn span. Scheduled sleep is the configured budget, while polling duration includes scheduling and request time; it is not provider processing time in isolation.

## Metric definitions

| Event / field | Start → end | Interpretation |
| --- | --- | --- |
| `voice_route_ready.setup_ms` | Session entry → route initialization | Includes local model/tool setup if attempted |
| `socket_open.connect_ms` | Handshake start → socket established | Excludes earlier route initialization |
| `utterance_endpoint.endpoint_wait_ms` | Last processed above-threshold mic chunk → endpoint | Speech-end proxy; includes scheduling, not acoustic truth |
| `utterance_dispatched.endpoint_to_send_ms` | Endpoint → turn control write completion | Server route; includes PCM conversion/write |
| `transcript.response_ms` | Endpoint → transcript received | Includes server STT and transport; local typed turns differ |
| `first_text_delta.response_ms` | Session start for greeting / endpoint for turn → first delta | Generation/network boundary |
| `first_audio_received.response_ms` | Same origin → first binary frame | Not playback |
| `first_pcm_rendered.response_ms` | Same origin → first PCM output callback | Includes decoding/resampling/queueing, or local TTS |
| `first_pcm_rendered.speech_end_to_render_ms` | Last processed voiced chunk → output callback | Closest measured user-response boundary; excludes unknown hardware/acoustic delay |
| `generation_done.response_ms` | Same origin → server done control | Not playback completion, especially with local synthesis jobs pending |
| `ping_rtt.rtt_ms` | Application ping write attempt → pong received | Includes both network directions and server/client scheduling |

All durations use monotonic clocks. Cross-machine timestamps must not be subtracted to infer one-way network delay. Null means not observed/applicable, not zero. First PCM may include synthesized leading silence; it is not guaranteed to be the first non-silent sound.

## Confirmed design delays and likely investigation targets

1. Server-audio turns wait for 650 ms of silence before submission. STT then uploads a complete WAV, creates a transcript job and polls after each 500 ms sleep. In the normal completed-poll path there is approximately 1,150 ms of configured waiting across endpointing and the first poll, before adding network, transcription, generation and TTS work. This is a code-level timing budget, not an observed latency result. It does not apply to local ASR or typed turns.
2. Greeting preparation includes route initialization before socket connection, audio-engine setup, Core context preparation, agent generation, sentence accumulation and TTS. New measurements separate these boundaries. There is no evidence yet identifying the dominant greeting phase.
3. Sentence buffering delays TTS until enough text forms a sentence. Local TTS additionally generates the complete sentence before PCM enqueue. Measure first text versus first rendered PCM before changing chunking.
4. Per-frame desktop diagnostics synchronously write and flush the local log file. This can add latency/jitter on the event loop and enlarge long-session logs. Measure its cost, then consider buffered asynchronous logging and aggregated frame metrics.
5. Microphone and sentence queues are unbounded. Sustained slow processing can increase queue age and memory use. Mic quality counters and endpoint timing do not fully measure capture-to-consumption backlog.
6. Current binary audio carries no wire-level turn identifier. Server cancellation and client active-turn filtering reduce stale playback, but cannot identify every frame already in flight. Tagged audio envelopes would provide stronger attribution.
7. Underrun counts include queue tail padding after actual audio ends. They are diagnostic indicators, not a precise count of audible glitches. Playback completion and physical output latency remain unmeasured.

Recommended order after collecting data: first confirm the actual route; attribute cold greeting setup; quantify endpoint/polling cost; compare first delta to first PCM; then investigate long-turn queue growth, interruption leakage and logging overhead. Do not prioritize a provider change based solely on static timing budgets.

## Validation

Core all-target/all-feature check and strict Clippy passed. Existing Core tests: 36 passed, 37 ignored, zero failures; ignored cases require integration infrastructure. Desktop native check passed and a debug `.app` was built. The final rebuilt bundle path is `/Users/rahul/Documents/vox/vox-desktop/target/debug/bundle/macos/Vox.app`.

Unfiltered strict desktop Clippy reports three existing findings: `auth.rs` unnecessary return, and eight-argument functions in `client.rs` and `wiz.rs`. Clippy with those two existing lint categories allowed passed. These findings were not hidden by source-level suppressions or unrelated edits. No code comments or repository test files were added.

## Remaining live run

Once the Mac is unlocked, open the rebuilt bundle and verify authentication and the selected route. Capture at least three cold starts, three warm starts, ten simple response turns, a continuous multi-turn conversation and interruption during playback. Use benign prompts and record failures as samples rather than discarding them. Keep cold/warm greetings and local/server routes separate. Record per-turn observations of transcription, context continuity, response text, playback and interruption.

After a call, run:

```sh
python3 /Users/rahul/Documents/vox/vox-deploy/workspace/scripts/analyze-voice-latency.py /Users/rahul/Documents/log.txt
```

The analyzer reports per-turn events, sample counts, medians and ranges, split by greeting/user turn. It does not calculate unsupported tail percentiles. Do not combine different route cohorts in one invocation. Deploy the Core changes before expecting the new server stage logs or server/client session mapping. The local desktop improvements can run against the older server, but missing metadata and cancellation fixes must be noted.

Additional controlled samples are still required. Build success and source review do not constitute end-to-end voice verification.

## Subsequent incoming phone call — 18:58 IST

After the initial report, a real incoming Twilio call supplied a failed-startup sample. Webhook-to-stream-start was 994 ms, STT connection was 838 ms, and the voice session ended at 839 ms before any greeting output. Bridge reported `Twilio audio buffer unavailable` and closed the media stream. These are server-side timings from a failed phone call, not desktop end-to-end latency or a successful greeting distribution. The initial zero-event query occurred before this call; the later query retrieved it.

See [call failure investigation](voice-call-cut-2026-10-10.md) for the timeline and startup queue saturation mechanism. This call does not complete the pending native desktop verification.

## Desktop observations after unlock — from 22:10 IST

One older-process and two instrumented desktop sessions ran against the existing Core deployment. The route was server ASR/agent/TTS; local voice models were unavailable. The first process still contained older logging code, so it was quit and the instrumented bundle relaunched.

| Boundary | Older process, first session | Instrumented session after restart |
| --- | ---: | ---: |
| WebSocket connection | 1,477 ms | 496 ms |
| Audio-engine initialization | 3,022 ms | 275 ms |
| First text delta from session entry | Unavailable | 952 ms |
| First received greeting frame | 5,305 ms | 1,079 ms |
| First greeting PCM output callback | Unavailable | 1,101.23 ms |
| First receipt → PCM callback | Unavailable | 21.992 ms |

The approximately 5.3-second slow greeting in the older process included 4.5 seconds of socket/audio initialization. The faster subsequent sample demonstrates startup variability; it does not isolate cache, hardware or network causality.

The instrumented greeting finished generation at 1,517 ms while about 2,682 ms of audio remained queued. This directly confirms that generation completion is not playback completion. Application ping samples included 140 ms and 49 ms; these are two RTT observations, not a network distribution.

The 51.4-second instrumented session submitted ten utterances, including very short threshold bursts and overlapping requests. A benign system speech prompt was played through the speakers as a microphone exercise. This is an uncontrolled acoustic environment, not a clean ten-turn benchmark. One later response reached the output callback 4,720.651 ms after the latest endpoint, but this interval is not accepted as a uniquely correlated user-turn sample. A transcript for an earlier request also arrived after a newer endpoint, demonstrating why the shared client timing origin can misattribute overlap when Core does not echo a client request ID.

The analyzer now conservatively excludes user-turn aggregates for sessions containing overlapping unresolved utterances. Raw events are retained with an exclusion notice. Per-utterance IDs echoed by Core and carried on audio frames are the next measurement improvement. Core's new cancellation logic was not deployed during this test.

A VAD issue merits investigation: 660–680 ms submitted buffers can mostly consist of the configured 650 ms silence tail. The minimum-buffer check counts that tail, so brief noise can pass the nominal 350 ms minimum. This may generate unwanted STT work and cancel legitimate pending responses. The samples establish admission behavior; they do not establish whether each burst was noise, echo or brief user speech.

The desktop session ended through the local stop path with no socket-close or WebSocket error preceding it. This is separate from the failed Twilio call investigated above. Interruption, semantic response accuracy, repeatable cold/warm cohorts, and year-scale/long-session performance have not been validated.

A subsequent instrumented session recorded greeting first PCM at 1,344.867 ms, with receipt-to-render delay 15.527 ms. Across the two greetings, the observed range is 1.10–1.34 seconds; two samples do not support a tail-latency conclusion. The second session also contains overlapping unresolved requests, so its user-turn timing aggregates are excluded. It was still active at the last log inspection; it is not claimed as a completed controlled conversation.
