# Map Scenes: Vox drives the 3D map

Status: draft for review. No backwards compatibility with old clients (all clients ship together).

## Goal
Vox (voice or background task) can put things on the 3D map on desktop and Android: fly the camera, drop pins, animate arcs, grow spend columns, highlight buildings. While Vox speaks, the map reacts. Adding a third client later means writing one small renderer, nothing else.

## Core idea: scene = state, not commands
Core owns one **MapScene** per user. Clients never interpret agent intent; they render the latest scene and keep nothing else.

- Voice WebSocket and bridge are **unchanged**. Scenes do not ride the voice socket, so they also work outside a call (task pins) through the same path.
- Full replacement, never deltas. Every push is the complete scene, so a late-joining or reconnecting client is correct after one fetch.
- Layers are keyed by id and the client diffs by id. No client-side ordering logic.

## Contract (single source of truth)
`vox-core/contracts/map-scene.schema.json`. Clients codegen or hand-mirror from it; nothing else defines the shape.

```
MapScene { rev:int, camera?:{lng,lat,zoom?,pitch?,bearing?,durationMs?},
           pins:[{id,lng,lat,label?,kind:place|task|spend}],
           arcs:[{id,from:[lng,lat],to:[lng,lat],label?,delayMs}],
           columns:[{id,lng,lat,value,label?}],
           highlights:[{id,lng,lat}],
           narrationHint?:string }
```
Empty scene = clear. `rev` is monotonic per user; clients drop anything older than what they hold.

## Delivery
- `GET /v1/map/scene` returns the current scene (client calls on app start, call start, reconnect).
- Live push: Core publishes the scene on the existing per-user realtime channel (`vox-core/src/realtime.rs`; desktop already consumes it as `vox-live-update`). Android has no live socket yet; it gets one on the same endpoint (`platform=android`).
- Scene store: latest scene per user, in memory inside `UserEventHub` (Redis is reserved for rebuildable projections of Postgres per `redis_keys.rs`), 30 min TTL so stale scenes clear themselves.

## Core agent tools (`vox-core/src/agents/tools/`)
- `show_on_map`: agent supplies camera/pins/arcs/columns/highlights; Core validates against the schema, bumps `rev`, stores, publishes.
- `clear_map`: publishes an empty scene.
- Spend and travel playback uses the existing data-read tools (`query_user_data`, location segments from `location_ingestion.rs`) and then `show_on_map`. No separate playback API. Arc `delayMs` provides the sequencing; the agent narrates using `narrationHint`.
- Task pins: durable task runs may carry an optional place. On run state change Core merges a `task` pin into the user's scene via the same publish path.

## Client architecture (identical on both)
Three small pieces per client, one responsibility each:

1. **SceneSource**: fetches `GET /v1/map/scene`, listens to the live channel, drops stale `rev`, exposes `current scene`.
2. **SceneRenderer**: pure function `render(map, scene)`. Replaces each GeoJSON source wholesale and updates MapLibre sources/layers (pins as markers, arcs as animated line layer, columns and highlights as `fill-extrusion`). Camera: `flyTo` when `camera.rev` changed.
3. **VoiceReactions**: reads `isSpeaking` / call state and drives pulse ring, building glow and orbit speed. Client-only, independent of scenes.

Desktop: `src/hooks/use-map-scene.ts` and `src/lib/map-scene.ts` beside `use-mission-map.ts`. Android: `map/MapSceneRenderer.kt` and `map/SceneSource.kt` beside `MissionMap.kt`. Orbit pauses while a scene has a camera and resumes when the scene is cleared or the call ends.

## Dead code to remove as part of this work
- `src/lib/map-highlight.ts` standalone highlight API on desktop, replaced by scene `highlights`; its Android equivalent likewise. Reusable geometry helpers (`outerRings`, `pointInRing`) move into the renderer only if still used.
- Empty directories `src/features/{pulse,spaces,spans}` and `src/components/spaces` in vox-desktop.
- Any desktop/Android code paths that existed only to feed the old highlight or ad-hoc marker calls.
Each removal is verified by grep for remaining references before deleting.

## Build order
1. Schema, Core scene store, `GET /v1/map/scene`, live publish, and a debug endpoint that posts a canned scene.
2. Desktop SceneSource + SceneRenderer; verify with the canned scene.
3. Android SceneSource + SceneRenderer; verify the same canned scene.
4. VoiceReactions on both.
5. `show_on_map` / `clear_map` tools wired into the agent, so voice requests drive the map.
6. Spend/travel playback prompts and arc sequencing polish.
7. Task pins.
8. Dead-code removal pass.

## Error handling
- Core rejects invalid scenes with a tool error the agent can see; clients only ever receive valid scenes.
- Clients ignore unknown/empty fields, never crash on a bad coordinate (skip that item).
- If the live channel drops, the next reconnect refetches the current scene.

## Open items to verify during the plan
- Resolved: Android needs a new live socket; visits are spans (`source='location'`, `category='visit'`, `data.lat/lng`); spend spans carry no coordinates, so spend columns sit on visit coordinates.
