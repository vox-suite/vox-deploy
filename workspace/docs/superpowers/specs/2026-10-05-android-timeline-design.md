# Android: native foundation + Timeline

Status: draft for review. Source of truth for behaviour is the desktop Timeline (`vox-desktop/src/components/{timeline-view,span-calendar,span-month-view,span-dialog}.tsx`, `lib/span-layout.ts`, `lib/span-format.ts`, `lib/schema-tokens.ts`). Same HTTP API as desktop; only the layout is adapted for phones. Spaces (full canvas), Pulse, Connected Apps, Activity logs are separate specs.

## Scope
1. Foundation: nav destinations, typed API client, shared live socket, ViewModel pattern, native UI kit.
2. Timeline: Day / Week / Month, span sheet (view/edit/delete + create), collection filter, live updates.

## API (identical to desktop `spansApi`)
All `POST` with bearer token, JSON snake_case.
- `/v1/spans/list` body `{from?, to?, collection_id?, status?, unscheduled?}` (ISO-8601 UTC) -> `Span[]`
- `/v1/spans` body `NewSpan` -> `Span`
- `/v1/spans/{id}/update` body `SpanPatch` -> `Span`
- `/v1/spans/{id}/delete` -> empty
- `/v1/collections/list` body `{}` -> `Collection[]`
- `/v1/collections/{cid}/spans/{sid}/add|remove` -> empty
- Live: existing `/v1/me/events/socket`; reload on events whose `type` starts with `span_` and on a reconnect.

Models (kotlinx.serialization, `ignoreUnknownKeys`): `Span` (id, parent_id, title, notes, category, source, schema_id, status, start_at, end_at, execution_type, data{amount?,currency?}, schema_color_token, schema_icon_token, collection_ids, version, ...), `Collection` (id, name, kind, status, starts_at, ends_at, span_count, version), enums `SpanStatus` (planned, active, waiting_user, done, failed, cancelled), `ExecutionType` (autonomous, interactive, manual_human), `CollectionKind` (trip, event, course, area, custom).

## Foundation
- **Navigation**: `Destination` enum (`Home`, `Timeline`; more added by later specs). Left pill shows one icon per destination; non-Home destinations render as full-screen layers over the map. Talk pill and avatar stay.
- **API client**: `net/VoxApi.kt` with `suspend inline fun <reified T> post(path, body)` over `VoxHttp`, shared `Json`, typed `ApiException(status, message)` (401 already routed via `VoxHttp.unauthorized`). `spans/SpansApi.kt` mirrors desktop's `spansApi`.
- **Live socket**: extract the socket loop from `map/scene/SceneSource.kt` into `net/LiveSocket.kt` exposing `events: SharedFlow<LiveEvent(type, raw)>` and a `reconnected` signal; `SceneSource` and Timeline both collect it. One socket per app.
- **State**: `androidx.lifecycle:lifecycle-viewmodel-compose`; one ViewModel per screen exposing a `StateFlow` of an immutable UI state.
- **UI kit** (`ui/kit/`): `VoxSheet` (modal bottom sheet, black theme), `VoxSegmented`, `VoxEmpty`, `VoxLoading`, `VoxErrorBar(retry)`, `VoxChip`. Reuses existing `VoxDarkScreen`, colours, fonts.

## Timeline behaviour (copied from desktop)
- **Modes** Day (default) / Week / Month. Anchor rules: Day keeps anchor; Week = Sunday of anchor's week; Month = first of month. Prev/Next: -1/+1 day, -7/+7 days, -1/+1 month. Week starts Sunday.
- **Range query**: Day = [anchor], Week = 7 days, Month = month grid (35 or 42 days: `monthGridDays`). `from = days.first` start, `to = last day + 1`.
- **Header**: date badge (month + day), title (collection name, else "Month YYYY"), range label (Day: "Weekday, Mon D, YYYY"; Week/Month: "Mon D – Mon D, YYYY"), collection kind badge when scoped, refresh button (spinner while loading).
- **Day grid**: 24h, 56dp/hour, 54dp gutter. Port of `layoutDay`/`layoutAllDay` exactly: cluster/column packing, nested children via `parent_id` (indent 10dp, 22 min header), instants (start==end) as pills, min block 25 min, spans >= 24h in the "all day" rows (24dp each). Current-time dashed line (updates every 60 s). Initial scroll: earliest span hour on shown days, else (today ? now-2h : 8h), minus 1 hour.
- **Block rendering**: category style = `schema_color_token` (OKLCH token 0-23 -> sRGB) else category map, else default slate; same bg/border/dot/subtext values. Time line only if block height >= 48dp. Amount chip when `data.amount` is a number (`formatMoney`, default INR). `cancelled`: 40% alpha + strikethrough; `active`: light ring + glow; `failed`: red ring. Parents render bg mixed 60% toward `#111215`.
- **Month**: grid of days, current month emphasised, others 40% alpha, today highlighted, per-day item count; tapping a day switches to Day view on that date. (Phone adaptation: coloured dots instead of text chips.)
- **Week** (phone adaptation): swipeable week strip (Sun-Sat, today highlighted) + agenda list for the selected day: all-day first, then by start time, each row = time range, title, category indicator, amount; tap opens sheet. Same query/range as desktop.
- **Span sheet** (replaces dialog): title, start/end (date+time pickers), category (free text + suggestions: todo, meeting, call, meal, expense, ride, travel, visit, reminder), status (6 values), notes, collections (toggle chips, only if any exist), and for **new** spans only: "Vox should" (Just log it / Do it for me / Do it, ask me first / Remind me) and Amount (INR). Header shows source badge and amount badge.
  - Save (existing): `update` with `{notes, category}` plus `{title, status, start_at, end_at}` unless `source == "google_calendar"` (then those fields are read-only with the same explanatory text). No `expected_version` (desktop doesn't send it). Then diff `collection_ids` and call collection `add`/`remove` per change.
  - Save (new): `create` with `{title, status, start_at, end_at, notes, category||"general", execution_type|null, data{amount,currency:"INR"}|{}, collection_ids}`; default status `done` if start is in the past else `planned`; default end = start + 1h. Create entry point is a "+" button (desktop's dialog supports create; its timeline view just never opens it).
  - Validation: title required ("Give it a title"); end must not precede start ("End must be after start"). Delete button for existing spans.
- **Collections filter**: chip row above the grid ("All" + each collection); selecting one sets `collection_id` on the query and the header title.
- **Refresh**: reload after any save/delete; on `span_*` live events and live reconnect; every 15 s while the Timeline is visible (desktop parity); pull-to-refresh and header button.

## Category indicator
Dot with glow by default. If `schema_icon_token` is set desktop shows one of 24 lucide icons; Android renders the same 24 as generated `ImageVector`s (`ui/kit/SchemaIcons.kt`, produced once from the lucide SVGs, ISC licence), falling back to the dot for unknown tokens.

## Files
New: `net/VoxApi.kt`, `net/LiveSocket.kt`, `spans/{SpanModels,SpansApi,SpanFormat,SpanLayout,SchemaTokens}.kt`, `timeline/{TimelineViewModel,TimelineScreen,DayGrid,WeekAgenda,MonthGrid,SpanSheet}.kt`, `ui/kit/*`.
Modified: `map/scene/SceneSource.kt` (use LiveSocket), `ui/VoxBottomNav.kt` (destinations), `MainActivity.kt` (host layers), `app/build.gradle.kts` (viewmodel-compose).
Pure logic (`SpanLayout`, `SpanFormat`, month-grid and range helpers) has no Android dependencies so it can be ported 1:1 from the TS and checked by reading.

## Errors
List errors show a `VoxErrorBar` with Retry (message from `ApiException`). Save/delete errors show inline in the sheet and keep it open. 401 signs out via the existing flow.

## Verification
No new test files (project preference). Verify on the emulator against a local Core: all three modes, nested/overlapping/instant/all-day spans, create/edit/delete, collection toggle, google_calendar read-only case, live update from a second client, offline error + retry.

## Out of scope
Pulse, Connected Apps, Activity logs, Spaces (own specs; Spaces will be the full canvas). Creating/editing collections. Widgets/notifications.
