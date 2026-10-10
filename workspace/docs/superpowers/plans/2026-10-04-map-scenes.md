# Map Scenes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vox (voice agent or background task) drives the 3D mission map on desktop and Android with camera moves, pins, arcs, spend columns and building highlights, and the map reacts while Vox talks.

**Architecture:** Core keeps one in-memory `MapScene` per user inside `UserEventHub` and pushes the full scene as a `map_scene` frame on the existing `/v1/me/events/socket`; clients also `GET /v1/me/map/scene` on start. Each client has a source (fetch + live), a renderer (five GeoJSON sources/layers, no DOM markers, so both platforms behave the same) and a reactions hook. The voice socket and bridge are untouched.

**Tech Stack:** Rust (axum, rig tools, serde), TypeScript (Tauri, maplibre-gl 6, `@vox/ui` platform ports), Kotlin (Compose, MapLibre Android, OkHttp, kotlinx.serialization).

**Spec:** `docs/superpowers/specs/2026-10-04-map-scenes-design.md`

**Deviations from the spec (found while reading code):**
- Scene store is in-memory in `UserEventHub`, not Redis: `vox-core/src/redis_keys.rs` declares Redis a rebuildable projection of Postgres only. Scenes are ephemeral (30 min TTL), lost on API restart.
- Renderer replaces each GeoJSON source wholesale on every scene instead of diffing by id. Same result, less code.
- Android has no live socket today; Task 3 adds one.
- The home-building highlight stays; it becomes a fixed first entry of the highlight set, so `map-highlight` is refactored, not deleted.
- Existing allowlist test `governed_tool_surface_tests` in `vox-core/src/agents/conversation.rs` pins the agent's tool names; Tasks 5 and 6 update it deliberately.

## Global Constraints

- No backwards compatibility; no legacy shims.
- No new test files and no code comments in new code (user preference). Each task ends with a runnable verification instead. The one existing test that must change is named above.
- Wire frame: `{"type":"map_scene","scene":MapScene}`; JSON is camelCase; coordinates are `lng`/`lat` degrees.
- Client rule: apply a scene when `scene.rev >= heldRev`, drop it otherwise.
- Max 50 items per list; zoom 10 to 19; fonts `["Noto Sans Regular"]` (the only font in the OpenFreeMap dark style; glyphs served by the style).
- Pin colours: place `#4cc9f0`, task `#ffd166`, spend `#ff6363`. Column and arc colour `#ff6363`. Highlight colour stays `#ff3b30`.
- Scene active = has camera, pins, arcs, columns or highlights. While active: map bounds lifted, zoom range 10 to 19, orbit paused. When it clears: home bounds restored, camera eases home, orbit resumes.
- Desktop paths are relative to `vox-desktop/`, Android to `vox-android/app/src/main/java/in/voxagent/mobile/`, Core to `vox-core/`.

## Review Focus

- Out-of-range or non-finite coordinates: Core rejects the whole scene (Task 1 verify); clients skip a bad item and still render the rest.
- Scene expires or is cleared while the app is open: map returns home, restores bounds, orbit resumes (Tasks 2 and 3 verify).
- Client connects or reconnects mid-scene: it must show the current scene after one fetch (Tasks 2 and 3 verify).
- Desktop and phone open at once: both receive every frame (Task 1 verify uses two sockets).
- Call ends while a scene is showing: scene stays until cleared or expired, orbit stays paused (Task 4 verify).
- Huge `value` or 50 columns: height is normalised to the largest value and capped at 300 m (Task 2 verify).

---

### Task 1: Core scene model, store, endpoints

**Files:**
- Create: `vox-core/src/map_scene.rs`
- Create: `vox-core/services/api/routes/map_scene.rs`
- Modify: `vox-core/src/lib.rs` (add `pub mod map_scene;` after `pub mod jobs;`)
- Modify: `vox-core/src/realtime.rs` (`UserEventHub`)
- Modify: `vox-core/services/api/routes/mod.rs` (add `pub mod map_scene;`)
- Modify: `vox-core/services/api/router.rs`

**Interfaces:**
- Produces: `vox_core::map_scene::{MapScene, Camera, Pin, PinKind, Arc, Column, Highlight}`, `MapScene::validate(&self) -> Result<(), String>`, `UserEventHub::set_scene(&self, Uuid, MapScene) -> MapScene` (assigns `rev`, stores, notifies), `UserEventHub::scene(&self, Uuid) -> MapScene`. HTTP: `GET /v1/me/map/scene`, temporary `POST /v1/me/map/scene` (removed in Task 8).

- [ ] **Step 1: Create `src/map_scene.rs`**

```rust
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use uuid::Uuid;

pub const MAX_ITEMS: usize = 50;

#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct MapScene {
    #[serde(default)]
    pub rev: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub camera: Option<Camera>,
    #[serde(default)]
    pub pins: Vec<Pin>,
    #[serde(default)]
    pub arcs: Vec<Arc>,
    #[serde(default)]
    pub columns: Vec<Column>,
    #[serde(default)]
    pub highlights: Vec<Highlight>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub narration_hint: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct Camera {
    pub lng: f64,
    pub lat: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub zoom: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pitch: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub bearing: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub duration_ms: Option<u32>,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum PinKind {
    Place,
    Task,
    Spend,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct Pin {
    pub id: String,
    pub lng: f64,
    pub lat: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    pub kind: PinKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub state: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub span_id: Option<Uuid>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct Arc {
    pub id: String,
    pub from: [f64; 2],
    pub to: [f64; 2],
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    #[serde(default)]
    pub delay_ms: u32,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct Column {
    pub id: String,
    pub lng: f64,
    pub lat: f64,
    pub value: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct Highlight {
    pub id: String,
    pub lng: f64,
    pub lat: f64,
}

fn coord(lng: f64, lat: f64) -> Result<(), String> {
    if lng.is_finite()
        && lat.is_finite()
        && (-180.0..=180.0).contains(&lng)
        && (-90.0..=90.0).contains(&lat)
    {
        Ok(())
    } else {
        Err(format!("coordinate out of range: {lng},{lat}"))
    }
}

fn ids<'a>(kind: &str, items: impl Iterator<Item = &'a str>) -> Result<(), String> {
    let mut seen = HashSet::new();
    for (n, id) in items.enumerate() {
        if n >= MAX_ITEMS {
            return Err(format!("{kind}: more than {MAX_ITEMS} items"));
        }
        if id.is_empty() || !seen.insert(id) {
            return Err(format!("{kind}: empty or duplicate id"));
        }
    }
    Ok(())
}

impl MapScene {
    pub fn validate(&self) -> Result<(), String> {
        if let Some(camera) = &self.camera {
            coord(camera.lng, camera.lat)?;
            if let Some(zoom) = camera.zoom
                && !(10.0..=19.0).contains(&zoom)
            {
                return Err("camera zoom must be between 10 and 19".into());
            }
        }
        ids("pins", self.pins.iter().map(|p| p.id.as_str()))?;
        ids("arcs", self.arcs.iter().map(|a| a.id.as_str()))?;
        ids("columns", self.columns.iter().map(|c| c.id.as_str()))?;
        ids("highlights", self.highlights.iter().map(|h| h.id.as_str()))?;
        for pin in &self.pins {
            coord(pin.lng, pin.lat)?;
        }
        for arc in &self.arcs {
            coord(arc.from[0], arc.from[1])?;
            coord(arc.to[0], arc.to[1])?;
        }
        for column in &self.columns {
            coord(column.lng, column.lat)?;
            if !column.value.is_finite() || column.value < 0.0 {
                return Err("column value must be finite and not negative".into());
            }
        }
        for highlight in &self.highlights {
            coord(highlight.lng, highlight.lat)?;
        }
        Ok(())
    }

    pub fn is_empty(&self) -> bool {
        self.camera.is_none()
            && self.pins.is_empty()
            && self.arcs.is_empty()
            && self.columns.is_empty()
            && self.highlights.is_empty()
    }
}
```

- [ ] **Step 2: Hub store in `src/realtime.rs`.** Add imports `use crate::map_scene::MapScene;` and `use std::time::Instant;` (check existing `std::time` import and merge). In the `UserEventHub` struct add the field, and add the methods inside `impl UserEventHub`:

```rust
const SCENE_TTL: Duration = Duration::from_secs(30 * 60);

pub struct UserEventHub {
    conns: Arc<Mutex<HashMap<Uuid, Vec<UserConnection>>>>,
    next_generation: Arc<std::sync::atomic::AtomicU64>,
    scenes: Arc<Mutex<HashMap<Uuid, (Instant, MapScene)>>>,
}

pub fn set_scene(&self, user_id: Uuid, mut scene: MapScene) -> MapScene {
    {
        let mut scenes = self.scenes.lock().expect("map scene lock poisoned");
        scene.rev = scenes.get(&user_id).map_or(0, |(_, s)| s.rev) + 1;
        scenes.insert(user_id, (Instant::now(), scene.clone()));
    }
    self.notify(
        user_id,
        serde_json::json!({ "type": "map_scene", "scene": scene }),
    );
    scene
}

pub fn scene(&self, user_id: Uuid) -> MapScene {
    match self.scenes.lock().expect("map scene lock poisoned").get(&user_id) {
        Some((at, scene)) if at.elapsed() < SCENE_TTL => scene.clone(),
        Some((_, scene)) => MapScene { rev: scene.rev, ..MapScene::default() },
        None => MapScene::default(),
    }
}
```
Keep the struct's existing derives (it already derives `Default`/`Clone`); only the new field and constant are added.

- [ ] **Step 3: Routes.** `routes/map_scene.rs`:

```rust
use axum::{Extension, Json, extract::State, http::StatusCode};
use vox_core::{domain::identity::Actor, map_scene::MapScene, realtime::UserEventHub};

pub async fn get_map_scene(
    State(hub): State<UserEventHub>,
    Extension(actor): Extension<Actor>,
) -> Json<MapScene> {
    Json(hub.scene(actor.user_id))
}

pub async fn post_map_scene(
    State(hub): State<UserEventHub>,
    Extension(actor): Extension<Actor>,
    Json(scene): Json<MapScene>,
) -> Result<Json<MapScene>, (StatusCode, String)> {
    scene
        .validate()
        .map_err(|e| (StatusCode::UNPROCESSABLE_ENTITY, e))?;
    Ok(Json(hub.set_scene(actor.user_id, scene)))
}
```
In `router.rs` add `map_scene::{get_map_scene, post_map_scene},` to the `routes::{...}` import list, and after `live_routes`:

```rust
    let map_scene_routes = Router::new()
        .route("/v1/me/map/scene", get(get_map_scene).post(post_map_scene))
        .with_state(state.user_events.clone());
```
then `.merge(map_scene_routes)` after `.merge(live_routes)`.

- [ ] **Step 4: Verify compile.** Run: `cd vox-core && cargo check` → expect no errors.

- [ ] **Step 5: Verify behaviour.** Start Core as in `vox-core/README.md`, open a socket in one shell (`websocat -H "Authorization: Bearer $VOX_TOKEN" --protocol vox.v1 "ws://localhost:PORT/v1/me/events/socket?platform=test"`; run it in two shells for two clients), then:

```bash
curl -s -X POST localhost:PORT/v1/me/map/scene -H "Authorization: Bearer $VOX_TOKEN" -H 'content-type: application/json' -d '{"camera":{"lng":80.2707,"lat":13.0827,"zoom":15},"pins":[{"id":"a","lng":80.2707,"lat":13.0827,"label":"Home","kind":"place"}],"arcs":[{"id":"r","from":[80.2707,13.0827],"to":[80.2500,13.0600],"delayMs":0}],"columns":[{"id":"c","lng":80.2600,"lat":13.0700,"value":1200}]}'
```
Expected: both sockets print `{"type":"map_scene","scene":{"rev":1,...}}`; `GET` returns the same scene; a second POST gives `rev` 2. POST with `"lat":999` returns 422 and neither socket prints anything.

- [ ] **Step 6: Commit** (`vox-core`): `git add -A && git commit -m "feat: per-user map scene store and endpoints"`

---

### Task 2: Desktop scene layer

**Files:**
- Create: `vox-desktop/src/lib/map-scene.ts`
- Create: `vox-desktop/src/lib/scene-source.ts`
- Modify: `vox-desktop/src/lib/map-highlight.ts`
- Modify: `vox-desktop/src/hooks/use-mission-map.ts`

**Interfaces:**
- Consumes: `platform()` from `@vox/ui` (`http.request`, `live.subscribe`); `BUILDINGS_LAYER`, `extrusionBeforeId` from `lib/map-style`.
- Produces: `MapScene` type; `subscribeMapScene(handler: (scene: MapScene) => void): () => void`; `createSceneLayer(map, opts): { apply(scene: MapScene): void; setHome(home: [number, number]): void; destroy(): void }`; in `map-highlight.ts`, `setHighlights(map, points: [number, number][]): void` replacing `highlightBuildingAt`.

- [ ] **Step 1: Refactor `lib/map-highlight.ts`.** Replace `highlightBuildingAt` (from its `export function` line to the end of the file) with a function that builds one footprint feature per point and writes them all:

```ts
function footprintAt(
  map: maplibregl.Map,
  lng: number,
  lat: number,
): GeoJSON.Feature | null {
  const point = map.project([lng, lat]);
  const hits = map.queryRenderedFeatures(
    [
      [point.x - 80, point.y - 80],
      [point.x + 80, point.y + 80],
    ],
    { layers: [BUILDINGS_LAYER] },
  );
  let building: maplibregl.MapGeoJSONFeature | null = null;
  let buildingRing: number[][] | null = null;
  let best = Infinity;
  for (const f of hits) {
    for (const ring of outerRings(f.geometry)) {
      const d = pointInRing(lng, lat, ring)
        ? -1
        : Math.min(...ring.map(([x, y]) => (x - lng) ** 2 + (y - lat) ** 2));
      if (d < best) {
        best = d;
        building = f;
        buildingRing = ring;
      }
    }
  }
  if (!building || !buildingRing) return null;
  const props = building.properties ?? {};
  const h = Number(props.render_height ?? props.height ?? 12) + 1;
  const cx = buildingRing.reduce((a, [x]) => a + x, 0) / buildingRing.length;
  const cy = buildingRing.reduce((a, [, y]) => a + y, 0) / buildingRing.length;
  return {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [
        buildingRing.map(([x, y]) => [
          cx + (x - cx) * 1.03,
          cy + (y - cy) * 1.03,
        ]),
      ],
    },
    properties: { ...props, render_height: h, height: h },
  };
}

export function setHighlights(
  map: maplibregl.Map,
  points: [number, number][],
): void {
  if (!map.getLayer(BUILDINGS_LAYER)) return;
  ensureHighlightLayer(map);
  const features = points
    .map(([lng, lat]) => footprintAt(map, lng, lat))
    .filter((f): f is GeoJSON.Feature => f !== null);
  (map.getSource(HIGHLIGHT_SOURCE) as maplibregl.GeoJSONSource | undefined)
    ?.setData({ type: "FeatureCollection", features });
}
```

- [ ] **Step 2: Create `lib/scene-source.ts`:**

```ts
import { platform } from "@vox/ui";
import type { MapScene } from "@/lib/map-scene";

export function subscribeMapScene(
  handler: (scene: MapScene) => void,
): () => void {
  let active = true;
  const unsubscribe = platform().live.subscribe((event) => {
    if (event.type === "map_scene") handler(event.scene as MapScene);
  });
  void platform()
    .http.request<MapScene>({ method: "GET", path: "/v1/me/map/scene" })
    .then((scene) => {
      if (active) handler(scene);
    })
    .catch(() => undefined);
  return () => {
    active = false;
    unsubscribe();
  };
}
```

- [ ] **Step 3: Create `lib/map-scene.ts`:**

```ts
import { setHighlights } from "@/lib/map-highlight";
import { extrusionBeforeId } from "@/lib/map-style";
import type { maplibregl } from "@/lib/maplibre";

export type PinKind = "place" | "task" | "spend";

export type MapScene = {
  rev: number;
  camera?: {
    lng: number;
    lat: number;
    zoom?: number;
    pitch?: number;
    bearing?: number;
    durationMs?: number;
  };
  pins: {
    id: string;
    lng: number;
    lat: number;
    label?: string;
    kind: PinKind;
    state?: string;
    spanId?: string;
  }[];
  arcs: {
    id: string;
    from: [number, number];
    to: [number, number];
    label?: string;
    delayMs: number;
  }[];
  columns: {
    id: string;
    lng: number;
    lat: number;
    value: number;
    label?: string;
  }[];
  highlights: { id: string; lng: number; lat: number }[];
  narrationHint?: string;
};

const PIN_SOURCE = "vox-scene-pins";
const ARC_SOURCE = "vox-scene-arcs";
const COLUMN_SOURCE = "vox-scene-columns";
const ARC_MS = 1200;
const ARC_STEPS = 40;
const COLUMN_HALF_M = 12;
const COLUMN_MIN_H = 30;
const COLUMN_MAX_H = 300;
const HIGHLIGHT_RETRY_MS = [0, 800, 1800, 3200];

const EMPTY: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

const valid = (lng: number, lat: number) =>
  Number.isFinite(lng) &&
  Number.isFinite(lat) &&
  Math.abs(lng) <= 180 &&
  Math.abs(lat) <= 90;

function arcPath(
  [x1, y1]: [number, number],
  [x2, y2]: [number, number],
): number[][] {
  const cx = (x1 + x2) / 2 - (y2 - y1) * 0.25;
  const cy = (y1 + y2) / 2 + (x2 - x1) * 0.25;
  return Array.from({ length: ARC_STEPS + 1 }, (_, i) => {
    const t = i / ARC_STEPS;
    const u = 1 - t;
    return [
      u * u * x1 + 2 * u * t * cx + t * t * x2,
      u * u * y1 + 2 * u * t * cy + t * t * y2,
    ];
  });
}

function square(lng: number, lat: number): number[][][] {
  const dLat = COLUMN_HALF_M / 111320;
  const dLng = dLat / Math.cos((lat * Math.PI) / 180);
  return [
    [
      [lng - dLng, lat - dLat],
      [lng + dLng, lat - dLat],
      [lng + dLng, lat + dLat],
      [lng - dLng, lat + dLat],
      [lng - dLng, lat - dLat],
    ],
  ];
}

function isActive(scene: MapScene) {
  return Boolean(
    scene.camera ||
      scene.pins.length ||
      scene.arcs.length ||
      scene.columns.length ||
      scene.highlights.length,
  );
}

function ensureLayers(map: maplibregl.Map) {
  if (map.getSource(PIN_SOURCE)) return;
  for (const id of [PIN_SOURCE, ARC_SOURCE, COLUMN_SOURCE]) {
    map.addSource(id, { type: "geojson", data: EMPTY });
  }
  map.addLayer(
    {
      id: "vox-scene-columns",
      type: "fill-extrusion",
      source: COLUMN_SOURCE,
      paint: {
        "fill-extrusion-color": "#ff6363",
        "fill-extrusion-height": ["get", "h"],
        "fill-extrusion-base": 0,
        "fill-extrusion-opacity": 0.85,
      },
    },
    extrusionBeforeId(map),
  );
  map.addLayer({
    id: "vox-scene-arcs",
    type: "line",
    source: ARC_SOURCE,
    layout: { "line-cap": "round" },
    paint: { "line-color": "#ff6363", "line-width": 2.5, "line-opacity": 0.9 },
  });
  map.addLayer({
    id: "vox-scene-pin-halo",
    type: "circle",
    source: PIN_SOURCE,
    paint: {
      "circle-radius": 14,
      "circle-color": ["get", "color"],
      "circle-opacity": 0.25,
      "circle-pitch-alignment": "map",
    },
  });
  map.addLayer({
    id: "vox-scene-pin-dot",
    type: "circle",
    source: PIN_SOURCE,
    paint: {
      "circle-radius": 6,
      "circle-color": ["get", "color"],
      "circle-stroke-width": 2,
      "circle-stroke-color": "#ffffff",
      "circle-pitch-alignment": "map",
    },
  });
  map.addLayer({
    id: "vox-scene-pin-label",
    type: "symbol",
    source: PIN_SOURCE,
    layout: {
      "text-field": ["get", "label"],
      "text-font": ["Noto Sans Regular"],
      "text-size": 12,
      "text-offset": [0, 1.4],
      "text-anchor": "top",
      "text-allow-overlap": true,
    },
    paint: {
      "text-color": "#ffffff",
      "text-halo-color": "#050607",
      "text-halo-width": 1.5,
    },
  });
}

const PIN_COLORS: Record<string, string> = {
  place: "#4cc9f0",
  task: "#ffd166",
  spend: "#ff6363",
};

export function createSceneLayer(
  map: maplibregl.Map,
  opts: {
    onActiveChange: (active: boolean) => void;
    onCamera: () => void;
  },
) {
  ensureLayers(map);
  let home: [number, number] | null = null;
  let lastRev = -1;
  let active = false;
  let highlights: [number, number][] = [];
  let raf: number | null = null;
  let startedAt = 0;
  let arcs: { points: number[][]; delayMs: number }[] = [];
  const timers: number[] = [];

  const paintHighlights = () => {
    timers.splice(0).forEach(clearTimeout);
    const paint = () =>
      setHighlights(map, home ? [home, ...highlights] : highlights);
    map.once("idle", paint);
    for (const ms of HIGHLIGHT_RETRY_MS) timers.push(window.setTimeout(paint, ms));
  };

  const frame = (now: number) => {
    const elapsed = now - startedAt;
    let running = false;
    const features: GeoJSON.Feature[] = arcs.map(({ points, delayMs }) => {
      const progress = Math.min(1, Math.max(0, (elapsed - delayMs) / ARC_MS));
      if (progress < 1) running = true;
      const count = Math.max(2, Math.ceil(progress * ARC_STEPS) + 1);
      return {
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: progress > 0 ? points.slice(0, count) : [],
        },
      };
    });
    (map.getSource(ARC_SOURCE) as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features,
    });
    raf = running ? requestAnimationFrame(frame) : null;
  };

  return {
    apply(scene: MapScene) {
      if (scene.rev < lastRev) return;
      const changed = scene.rev !== lastRev;
      lastRev = scene.rev;

      const pinFeatures = scene.pins
        .filter((p) => valid(p.lng, p.lat))
        .map((p) => ({
          type: "Feature" as const,
          properties: {
            id: p.id,
            label: p.label ?? "",
            color: PIN_COLORS[p.kind] ?? PIN_COLORS.place,
            state: p.state ?? "",
          },
          geometry: { type: "Point" as const, coordinates: [p.lng, p.lat] },
        }));
      (map.getSource(PIN_SOURCE) as maplibregl.GeoJSONSource).setData({
        type: "FeatureCollection",
        features: pinFeatures,
      });

      const goodColumns = scene.columns.filter((c) => valid(c.lng, c.lat));
      const max = Math.max(1, ...goodColumns.map((c) => c.value));
      (map.getSource(COLUMN_SOURCE) as maplibregl.GeoJSONSource).setData({
        type: "FeatureCollection",
        features: goodColumns.map((c) => ({
          type: "Feature" as const,
          properties: {
            h: COLUMN_MIN_H + (COLUMN_MAX_H - COLUMN_MIN_H) * (c.value / max),
          },
          geometry: { type: "Polygon" as const, coordinates: square(c.lng, c.lat) },
        })),
      });

      arcs = scene.arcs
        .filter((a) => valid(...a.from) && valid(...a.to))
        .map((a) => ({ points: arcPath(a.from, a.to), delayMs: a.delayMs }));
      if (changed) startedAt = performance.now();
      if (raf != null) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(frame);

      highlights = scene.highlights
        .filter((h) => valid(h.lng, h.lat))
        .map((h) => [h.lng, h.lat]);
      paintHighlights();

      const nowActive = isActive(scene);
      if (nowActive !== active) {
        active = nowActive;
        opts.onActiveChange(nowActive);
      }
      if (changed && scene.camera && valid(scene.camera.lng, scene.camera.lat)) {
        const c = scene.camera;
        opts.onCamera();
        map.flyTo({
          center: [c.lng, c.lat],
          zoom: c.zoom ?? 16,
          pitch: c.pitch ?? 60,
          bearing: c.bearing ?? map.getBearing(),
          duration: c.durationMs ?? 2500,
          essential: true,
        });
      }
    },
    setHome(point: [number, number]) {
      home = point;
      paintHighlights();
    },
    destroy() {
      if (raf != null) cancelAnimationFrame(raf);
      timers.splice(0).forEach(clearTimeout);
    },
  };
}
```

- [ ] **Step 4: Wire into `hooks/use-mission-map.ts`.**
  - Replace `import { highlightBuildingAt } from "@/lib/map-highlight";` with `import { createSceneLayer } from "@/lib/map-scene";` and `import { subscribeMapScene } from "@/lib/scene-source";`.
  - Add refs near the others: `const sceneActive = useRef(false);` and `const sceneLayerRef = useRef<ReturnType<typeof createSceneLayer> | null>(null);` and `const unsubScene = useRef<(() => void) | null>(null);`.
  - Orbit: change `const running = now >= orbitPausedUntil.current && !map.isMoving();` to `const running = now >= orbitPausedUntil.current && !map.isMoving() && !sceneActive.current;`.
  - In `applyPosition`, delete the `paintHighlight` const, its `map.once("moveend"…)`, `map.once("idle"…)` and the three `window.setTimeout(paintHighlight…)` lines; replace with `sceneLayerRef.current?.setHome([lng, lat]);`.
  - In `map.on("load", …)`, right after `ensure3dBuildings(map);` add:

```ts
        const layer = createSceneLayer(map, {
          onCamera: () => pauseOrbit(3_600_000),
          onActiveChange: (active) => {
            sceneActive.current = active;
            const home = userLngLat.current;
            if (active) {
              map.setMaxBounds(null);
              map.setMinZoom(10);
              map.setMaxZoom(19);
            } else if (home) {
              setHomeBounds(map, home[0], home[1]);
              map.easeTo({
                center: home,
                zoom: MAP_ZOOM,
                pitch: MAP_PITCH,
                duration: 1800,
              });
            }
          },
        });
        sceneLayerRef.current = layer;
        if (userLngLat.current) layer.setHome(userLngLat.current);
        unsubScene.current = subscribeMapScene(layer.apply);
```
  - In the effect cleanup (before `marker.remove()`): `unsubScene.current?.(); unsubScene.current = null; sceneLayerRef.current?.destroy(); sceneLayerRef.current = null;`.
  - `setHomeBounds` and the load-time `map.setMaxBounds` calls stay; `applyPosition` calls `setHomeBounds` unconditionally, so guard it: `if (!sceneActive.current) setHomeBounds(map, lng, lat);`.

- [ ] **Step 5: Verify build.** Run: `cd vox-desktop && npx tsc --noEmit && npm run lint` → expect both clean.

- [ ] **Step 6: Verify visually.** Run `npm run tauri dev`, sign in, then POST the canned scene from Task 1 step 5. Expected: camera flies to the scene, "Home" pin with label, arc draws over ~1.2 s, one coral column rises. POST `{}`: map eases back home, orbit resumes. Restart the app mid-scene: scene reappears after launch. POST a scene with `"value":1e12` plus 49 more columns: tallest column stops at 300 m. Check `read_console_messages`/devtools for errors.

- [ ] **Step 7: Commit** (`vox-desktop`): `git add -A && git commit -m "feat: render map scenes on desktop"`

---

### Task 3: Android scene layer and live socket

**Files:**
- Create: `map/scene/MapScene.kt`, `map/scene/SceneSource.kt`, `map/scene/SceneRenderer.kt`
- Modify: `net/VoxHttp.kt` (add `getJson`)
- Modify: `map/MissionMap.kt`
- Modify: `MainActivity.kt` (pass token into the map)

**Interfaces:**
- Produces: `@Serializable data class MapScene(...)` mirroring the Task 1 JSON; `class SceneSource(context, tokenProvider)` with `val scenes: SharedFlow<MapScene>`, `start()`, `stop()`; `class SceneRenderer(map, onActiveChange, onCamera)` with `ensure(style)`, `apply(scene)`, `setHome(LatLng)`, `destroy()`.
- Consumes: `internal` helpers from `MissionMap.kt` made visible in step 1.

- [ ] **Step 1: Make shared helpers `internal` in `MissionMap.kt`.** Change `private` to `internal` on: `BUILDINGS_LAYER`, `HIGHLIGHT_SOURCE`, `HIGHLIGHT_LAYER`, `fun extrusionBeforeId`, `fun outerRings`, `fun pointInRing`. Replace the old single-point `highlightBuildingAt(map, loc)` (the whole function, bottom half of which sets `src.setGeoJson`) with:

```kotlin
private fun footprintAt(map: MapLibreMap, loc: LatLng): Feature? {
    val style = map.style ?: return null
    if (style.getLayer(BUILDINGS_LAYER) == null) return null
    val point = map.projection.toScreenLocation(loc)
    val box = RectF(point.x - 80f, point.y - 80f, point.x + 80f, point.y + 80f)
    val hits = map.queryRenderedFeatures(box, BUILDINGS_LAYER)
    var bestRing: List<Point>? = null
    var bestProps: JsonObject? = null
    var best = Double.MAX_VALUE
    for (feature in hits) {
        for (ring in outerRings(feature.geometry())) {
            val d = if (pointInRing(loc.longitude, loc.latitude, ring)) {
                -1.0
            } else {
                ring.minOf { (it.longitude() - loc.longitude).let { lx -> lx * lx } + (it.latitude() - loc.latitude).let { ly -> ly * ly } }
            }
            if (d < best) {
                best = d
                bestRing = ring
                bestProps = feature.properties()
            }
        }
    }
    val ring = bestRing ?: return null
    val props = bestProps ?: JsonObject()
    val h = (
        props.get("render_height")?.takeIf { !it.isJsonNull }?.asDouble
            ?: props.get("height")?.takeIf { !it.isJsonNull }?.asDouble
            ?: 12.0
        ) + 1.0
    val cx = ring.sumOf { it.longitude() } / ring.size
    val cy = ring.sumOf { it.latitude() } / ring.size
    val scaled = ring.map { Point.fromLngLat(cx + (it.longitude() - cx) * 1.03, cy + (it.latitude() - cy) * 1.03) }
    val outProps = JsonObject().apply {
        for ((k, v) in props.entrySet()) add(k, v)
        addProperty("render_height", h)
        addProperty("height", h)
    }
    return Feature.fromGeometry(Polygon.fromLngLats(listOf(scaled)), outProps)
}

internal fun setHighlights(map: MapLibreMap, points: List<LatLng>) {
    val src = map.style?.getSource(HIGHLIGHT_SOURCE) as? GeoJsonSource ?: return
    src.setGeoJson(FeatureCollection.fromFeatures(points.mapNotNull { footprintAt(map, it) }))
}
```
In `applyHome`, replace the `OnCameraIdleListener` block (the one calling `highlightBuildingAt`) with `sceneRenderer?.setHome(loc)`; add a field `private var sceneRenderer: SceneRenderer? = null` to `MissionMapController`.

- [ ] **Step 2: Create `map/scene/MapScene.kt`:**

```kotlin
package `in`.voxagent.mobile.map.scene

import kotlinx.serialization.Serializable

@Serializable
data class MapScene(
    val rev: Long = 0,
    val camera: SceneCamera? = null,
    val pins: List<ScenePin> = emptyList(),
    val arcs: List<SceneArc> = emptyList(),
    val columns: List<SceneColumn> = emptyList(),
    val highlights: List<SceneHighlight> = emptyList(),
    val narrationHint: String? = null,
) {
    val isActive get() = camera != null || pins.isNotEmpty() || arcs.isNotEmpty() ||
        columns.isNotEmpty() || highlights.isNotEmpty()
}

@Serializable
data class SceneCamera(
    val lng: Double,
    val lat: Double,
    val zoom: Double? = null,
    val pitch: Double? = null,
    val bearing: Double? = null,
    val durationMs: Int? = null,
)

@Serializable
data class ScenePin(
    val id: String,
    val lng: Double,
    val lat: Double,
    val label: String? = null,
    val kind: String,
    val state: String? = null,
    val spanId: String? = null,
)

@Serializable
data class SceneArc(
    val id: String,
    val from: List<Double>,
    val to: List<Double>,
    val label: String? = null,
    val delayMs: Int = 0,
)

@Serializable
data class SceneColumn(
    val id: String,
    val lng: Double,
    val lat: Double,
    val value: Double,
    val label: String? = null,
)

@Serializable
data class SceneHighlight(val id: String, val lng: Double, val lat: Double)
```

- [ ] **Step 3: Add `getJson` to `net/VoxHttp.kt`** next to `postJson`:

```kotlin
    suspend fun getJson(path: String, bearerToken: String? = null): String =
        execute(Request.Builder().url(url(path)).get(), bearerToken)
```
and make `url` `internal` (it is `private`; `SceneSource` needs the base URL for the socket, which it derives itself from `BuildConfig.VOX_API_BASE_URL` like `VoiceSession`, so no change to `url`).

- [ ] **Step 4: Create `map/scene/SceneSource.kt`:**

```kotlin
package `in`.voxagent.mobile.map.scene

import `in`.voxagent.mobile.BuildConfig
import `in`.voxagent.mobile.net.VoxHttp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

class SceneSource(private val token: () -> String?) {
    private val json = Json { ignoreUnknownKeys = true }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val _scenes = MutableSharedFlow<MapScene>(replay = 1, extraBufferCapacity = 8)
    val scenes: SharedFlow<MapScene> = _scenes.asSharedFlow()
    private var job: Job? = null
    private var socket: WebSocket? = null

    fun start() {
        if (job != null) return
        job = scope.launch {
            while (isActive) {
                val bearer = token()
                if (bearer != null) {
                    runCatching {
                        val body = VoxHttp.getJson("/v1/me/map/scene", bearer)
                        _scenes.emit(json.decodeFromString<MapScene>(body))
                    }
                    connect(bearer)
                }
                delay(RETRY_MS)
            }
        }
    }

    fun stop() {
        job?.cancel()
        job = null
        socket?.close(1000, "stop")
        socket = null
    }

    private suspend fun connect(bearer: String) {
        val closed = kotlinx.coroutines.CompletableDeferred<Unit>()
        val base = BuildConfig.VOX_API_BASE_URL.trimEnd('/').let {
            when {
                it.startsWith("https://") -> "wss://" + it.removePrefix("https://")
                it.startsWith("http://") -> "ws://" + it.removePrefix("http://")
                else -> "ws://$it"
            }
        }
        val request = Request.Builder()
            .url("$base/v1/me/events/socket?platform=android")
            .header("Authorization", "Bearer $bearer")
            .header("Sec-WebSocket-Protocol", "vox.v1")
            .build()
        socket = VoxHttp.client.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching {
                    val frame: JsonObject = json.parseToJsonElement(text).jsonObject
                    if (frame["type"]?.jsonPrimitive?.content == "map_scene") {
                        val scene = json.decodeFromJsonElement(MapScene.serializer(), frame.getValue("scene"))
                        _scenes.tryEmit(scene)
                    }
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                closed.complete(Unit)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                closed.complete(Unit)
            }
        })
        closed.await()
    }

    private companion object {
        const val RETRY_MS = 5_000L
    }
}
```
(`VoxHttp.client` has a 20 s read timeout; the server pings every 20 s, which keeps it open. If the socket drops at idle during verification, set `.pingInterval(20, TimeUnit.SECONDS)` on `VoxHttp.client`.)

- [ ] **Step 5: Create `map/scene/SceneRenderer.kt`:**

```kotlin
package `in`.voxagent.mobile.map.scene

import android.view.Choreographer
import `in`.voxagent.mobile.map.extrusionBeforeId
import `in`.voxagent.mobile.map.setHighlights
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.Style
import org.maplibre.android.style.expressions.Expression
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.FillExtrusionLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.Property
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.SymbolLayer
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point
import org.maplibre.geojson.Polygon
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min

private const val PIN_SOURCE = "vox-scene-pins"
private const val ARC_SOURCE = "vox-scene-arcs"
private const val COLUMN_SOURCE = "vox-scene-columns"
private const val ARC_MS = 1200.0
private const val ARC_STEPS = 40
private const val COLUMN_HALF_M = 12.0
private const val COLUMN_MIN_H = 30.0
private const val COLUMN_MAX_H = 300.0
private val HIGHLIGHT_RETRY_MS = longArrayOf(0, 800, 1800, 3200)

private val PIN_COLORS = mapOf("place" to "#4cc9f0", "task" to "#ffd166", "spend" to "#ff6363")

private fun valid(lng: Double, lat: Double) =
    lng.isFinite() && lat.isFinite() && kotlin.math.abs(lng) <= 180 && kotlin.math.abs(lat) <= 90

private fun arcPath(from: List<Double>, to: List<Double>): List<Point> {
    val (x1, y1) = from
    val (x2, y2) = to
    val cx = (x1 + x2) / 2 - (y2 - y1) * 0.25
    val cy = (y1 + y2) / 2 + (x2 - x1) * 0.25
    return (0..ARC_STEPS).map { i ->
        val t = i.toDouble() / ARC_STEPS
        val u = 1 - t
        Point.fromLngLat(u * u * x1 + 2 * u * t * cx + t * t * x2, u * u * y1 + 2 * u * t * cy + t * t * y2)
    }
}

private fun square(lng: Double, lat: Double): Polygon {
    val dLat = COLUMN_HALF_M / 111320.0
    val dLng = dLat / cos(Math.toRadians(lat))
    return Polygon.fromLngLats(
        listOf(
            listOf(
                Point.fromLngLat(lng - dLng, lat - dLat),
                Point.fromLngLat(lng + dLng, lat - dLat),
                Point.fromLngLat(lng + dLng, lat + dLat),
                Point.fromLngLat(lng - dLng, lat + dLat),
                Point.fromLngLat(lng - dLng, lat - dLat),
            ),
        ),
    )
}

class SceneRenderer(
    private val map: MapLibreMap,
    private val onActiveChange: (Boolean) -> Unit,
    private val onCamera: () -> Unit,
) {
    private var home: LatLng? = null
    private var lastRev = -1L
    private var active = false
    private var highlights: List<LatLng> = emptyList()
    private var arcs: List<Pair<List<Point>, Int>> = emptyList()
    private var startedAt = 0L
    private var framing = false
    private val choreographer = Choreographer.getInstance()
    private val handler = android.os.Handler(android.os.Looper.getMainLooper())

    private val frame = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            val elapsed = (System.nanoTime() - startedAt) / 1_000_000.0
            var running = false
            val features = arcs.map { (points, delayMs) ->
                val progress = min(1.0, max(0.0, (elapsed - delayMs) / ARC_MS))
                if (progress < 1.0) running = true
                val count = max(2, kotlin.math.ceil(progress * ARC_STEPS).toInt() + 1)
                Feature.fromGeometry(LineString.fromLngLats(if (progress > 0) points.take(count) else emptyList()))
            }
            (map.style?.getSource(ARC_SOURCE) as? GeoJsonSource)?.setGeoJson(FeatureCollection.fromFeatures(features))
            framing = running
            if (running) choreographer.postFrameCallback(this)
        }
    }

    fun ensure(style: Style) {
        if (style.getSource(PIN_SOURCE) != null) return
        for (id in listOf(PIN_SOURCE, ARC_SOURCE, COLUMN_SOURCE)) {
            style.addSource(GeoJsonSource(id, FeatureCollection.fromFeatures(emptyList())))
        }
        val columns = FillExtrusionLayer("vox-scene-columns", COLUMN_SOURCE).withProperties(
            PropertyFactory.fillExtrusionColor("#ff6363"),
            PropertyFactory.fillExtrusionHeight(Expression.get("h")),
            PropertyFactory.fillExtrusionBase(0f),
            PropertyFactory.fillExtrusionOpacity(0.85f),
        )
        val before = extrusionBeforeId(style)
        if (before != null) style.addLayerBelow(columns, before) else style.addLayer(columns)
        style.addLayer(
            LineLayer("vox-scene-arcs", ARC_SOURCE).withProperties(
                PropertyFactory.lineColor("#ff6363"),
                PropertyFactory.lineWidth(2.5f),
                PropertyFactory.lineOpacity(0.9f),
                PropertyFactory.lineCap(Property.LINE_CAP_ROUND),
            ),
        )
        style.addLayer(
            CircleLayer("vox-scene-pin-halo", PIN_SOURCE).withProperties(
                PropertyFactory.circleRadius(14f),
                PropertyFactory.circleColor(Expression.get("color")),
                PropertyFactory.circleOpacity(0.25f),
                PropertyFactory.circlePitchAlignment(Property.CIRCLE_PITCH_ALIGNMENT_MAP),
            ),
        )
        style.addLayer(
            CircleLayer("vox-scene-pin-dot", PIN_SOURCE).withProperties(
                PropertyFactory.circleRadius(6f),
                PropertyFactory.circleColor(Expression.get("color")),
                PropertyFactory.circleStrokeWidth(2f),
                PropertyFactory.circleStrokeColor("#ffffff"),
                PropertyFactory.circlePitchAlignment(Property.CIRCLE_PITCH_ALIGNMENT_MAP),
            ),
        )
        style.addLayer(
            SymbolLayer("vox-scene-pin-label", PIN_SOURCE).withProperties(
                PropertyFactory.textField(Expression.get("label")),
                PropertyFactory.textFont(arrayOf("Noto Sans Regular")),
                PropertyFactory.textSize(12f),
                PropertyFactory.textOffset(arrayOf(0f, 1.4f)),
                PropertyFactory.textAnchor(Property.TEXT_ANCHOR_TOP),
                PropertyFactory.textAllowOverlap(true),
                PropertyFactory.textColor("#ffffff"),
                PropertyFactory.textHaloColor("#050607"),
                PropertyFactory.textHaloWidth(1.5f),
            ),
        )
    }

    private fun paintHighlights() {
        handler.removeCallbacksAndMessages(null)
        for (ms in HIGHLIGHT_RETRY_MS) {
            handler.postDelayed({ setHighlights(map, listOfNotNull(home) + highlights) }, ms)
        }
    }

    fun setHome(point: LatLng) {
        home = point
        paintHighlights()
    }

    fun apply(scene: MapScene) {
        if (scene.rev < lastRev) return
        val changed = scene.rev != lastRev
        lastRev = scene.rev
        val style = map.style ?: return

        (style.getSource(PIN_SOURCE) as? GeoJsonSource)?.setGeoJson(
            FeatureCollection.fromFeatures(
                scene.pins.filter { valid(it.lng, it.lat) }.map {
                    Feature.fromGeometry(Point.fromLngLat(it.lng, it.lat)).apply {
                        addStringProperty("id", it.id)
                        addStringProperty("label", it.label ?: "")
                        addStringProperty("color", PIN_COLORS[it.kind] ?: PIN_COLORS.getValue("place"))
                        addStringProperty("state", it.state ?: "")
                    }
                },
            ),
        )

        val columns = scene.columns.filter { valid(it.lng, it.lat) }
        val maxValue = max(1.0, columns.maxOfOrNull { it.value } ?: 1.0)
        (style.getSource(COLUMN_SOURCE) as? GeoJsonSource)?.setGeoJson(
            FeatureCollection.fromFeatures(
                columns.map {
                    Feature.fromGeometry(square(it.lng, it.lat)).apply {
                        addNumberProperty("h", COLUMN_MIN_H + (COLUMN_MAX_H - COLUMN_MIN_H) * (it.value / maxValue))
                    }
                },
            ),
        )

        arcs = scene.arcs
            .filter { it.from.size == 2 && it.to.size == 2 && valid(it.from[0], it.from[1]) && valid(it.to[0], it.to[1]) }
            .map { arcPath(it.from, it.to) to it.delayMs }
        if (changed) startedAt = System.nanoTime()
        choreographer.removeFrameCallback(frame)
        choreographer.postFrameCallback(frame)

        highlights = scene.highlights.filter { valid(it.lng, it.lat) }.map { LatLng(it.lat, it.lng) }
        paintHighlights()

        if (scene.isActive != active) {
            active = scene.isActive
            onActiveChange(active)
        }
        val camera = scene.camera
        if (changed && camera != null && valid(camera.lng, camera.lat)) {
            onCamera()
            map.easeCamera(
                CameraUpdateFactory.newCameraPosition(
                    CameraPosition.Builder()
                        .target(LatLng(camera.lat, camera.lng))
                        .zoom(camera.zoom ?: 16.0)
                        .tilt(camera.pitch ?: 60.0)
                        .bearing(camera.bearing ?: map.cameraPosition.bearing)
                        .build(),
                ),
                camera.durationMs ?: 2500,
            )
        }
    }

    fun destroy() {
        choreographer.removeFrameCallback(frame)
        handler.removeCallbacksAndMessages(null)
    }
}
```
`extrusionBeforeId(style: Style)` and `setHighlights` are the `internal` members from step 1; `Feature.addStringProperty`/`addNumberProperty` are the MapLibre geojson API.

- [ ] **Step 6: Wire into `MissionMapController` (`MissionMap.kt`).**
  - Change the composable and controller signatures: `MissionMapBackground(modifier, locationPermissionGranted, token: () -> String?)` and `MissionMapController(context, token)`. In `MainActivity.kt` line ~575 pass `token = { latestToken }` (`latestToken` is already declared at the top of that composable).
  - Add to the controller: `private var sceneActive = false`, `private val sceneSource = SceneSource(token)`, `private var sceneJob: Job? = null`.
  - In `map.setStyle(...) { style -> ... }` after `addYouLayer(style)`:

```kotlin
                val renderer = SceneRenderer(
                    map,
                    onActiveChange = { active ->
                        sceneActive = active
                        if (active) {
                            map.setLatLngBoundsForCameraTarget(null)
                            map.setMinZoomPreference(10.0)
                            map.setMaxZoomPreference(19.0)
                        } else {
                            homeCenter?.let { applyHome(map, it) }
                        }
                    },
                    onCamera = { orbit?.pause(3_600_000) },
                )
                renderer.ensure(style)
                sceneRenderer = renderer
                homeCenter?.let { renderer.setHome(it) }
                sceneJob = CoroutineScope(Dispatchers.Main).launch {
                    sceneSource.scenes.collect { renderer.apply(it) }
                }
                sceneSource.start()
```
  - `OrbitController(map) { homeCenter }`: change the lambda to `{ if (sceneActive) null else homeCenter }` (orbit does nothing while the centre is null).
  - In `applyHome`, skip the bounds and `easeCamera` when a scene is active: not needed because `applyHome` is only called from `applyLocation` (location resolved at start) and from the `onActiveChange(false)` branch above; add `if (sceneActive) return` as the first line of `applyHome`'s caller in `applyLocation`.
  - In `destroy()`: `sceneJob?.cancel(); sceneSource.stop(); sceneRenderer?.destroy()`.
  - Add imports: `in.voxagent.mobile.map.scene.SceneRenderer`, `SceneSource`, `kotlinx.coroutines.CoroutineScope`, `Dispatchers`, `Job`, `launch`.

- [ ] **Step 7: Verify build.** Run: `cd vox-android && ./gradlew :app:assembleDebug` → expect BUILD SUCCESSFUL.

- [ ] **Step 8: Verify on device/emulator.** Install, sign in, POST the Task 1 canned scene. Expected: same behaviour as desktop (fly, Home pin with label, arc draws, column). POST `{}`: eases home and orbit resumes. Force-stop and reopen with a scene active: scene shown after the initial fetch. Run desktop and phone together: both react to one POST.

- [ ] **Step 9: Commit** (`vox-android`): `git add -A && git commit -m "feat: render map scenes on android with live socket"`

---

### Task 4: Voice reactions on both clients

**Files:**
- Modify: `vox-desktop/src-tauri/src/types.rs`, `session.rs`, `client.rs`
- Modify: `vox-desktop/src/lib/tauri.ts`, `hooks/use-call-session.ts`, `app.tsx`, `components/home-shell.tsx`, `hooks/use-mission-map.ts`, `index.css`
- Modify: Android `voice/VoiceSession.kt`, `MainActivity.kt`, `map/MissionMap.kt`

**Interfaces:**
- Produces: desktop `CallStatus.is_vox_speaking: bool`; `useCallSession().isVoxSpeaking`; `useMissionMap({ callActive, voxSpeaking })`; Android `VoiceSession.isVoxSpeaking(): Boolean`; `MissionMapBackground(..., callActive: Boolean, voxSpeaking: Boolean)`.
- Reaction rule (identical both): call active → orbit speed factor 0.35 and steady glow on the home pin; Vox speaking → pin ring pulses and highlight opacity oscillates between 0.7 and 1.0 at about 4.5 rad/s.

- [ ] **Step 1: Desktop Rust.** `types.rs`: add `pub is_vox_speaking: bool,` to `CallStatus`. `session.rs`: add `vox_playing: Arc<AtomicBool>` to `ActiveSession`; in `start_call` create `let vox_playing = Arc::new(AtomicBool::new(false)); let vox_playing_clone = Arc::clone(&vox_playing);`, store `vox_playing: Arc::clone(&vox_playing)` in the struct literal, pass `vox_playing_clone` as a new last argument to `client::run_session_loop`. Change `status_from_phase(phase, is_running, mic_level)` to take `vox_playing: bool` and set `is_vox_speaking: is_running && phase == PHASE_ACTIVE && vox_playing`; update the five call sites (`call_status` reads `session.vox_playing.load(Ordering::Relaxed)`; the others pass `false`). `client.rs`: add `vox_playing: Arc<AtomicBool>` as the last parameter of `run_session_loop` and, after `let playing = audio_engine.is_playing();` add `vox_playing.store(playing, Ordering::Relaxed);`. Ensure `AtomicBool` and `Ordering` are imported in `client.rs`.
- [ ] **Step 2: Desktop TS.** `lib/tauri.ts` `CallStatus`: add `is_vox_speaking: boolean;`. `use-call-session.ts`: add `const [isVoxSpeaking, setIsVoxSpeaking] = useState(false);`, set it from `status.is_vox_speaking` in the poll, reset to `false` in `endCall`, `resetCallState` and the idle/ended branch, and return it. `app.tsx`: destructure `isVoxSpeaking` and pass `voxSpeaking={isVoxSpeaking}` to `<HomeShell>`. `home-shell.tsx`: add `voxSpeaking: boolean` to props and call `useMissionMap({ callActive: isActive, voxSpeaking })`.
- [ ] **Step 3: Desktop map hook.** In `use-mission-map.ts`: signature `useMissionMap(reaction: { callActive: boolean; voxSpeaking: boolean })`; add `const reactionRef = useRef(reaction); reactionRef.current = reaction;` before the effects. In the orbit frame replace `((running ? 1 : 0) - orbitSpeed)` with `((running ? (reactionRef.current.callActive ? 0.35 : 1) : 0) - orbitSpeed)`. At the top of `frame` after `orbitLastTs.current = now;` add:

```ts
          const { callActive, voxSpeaking } = reactionRef.current;
          el.classList.toggle("vox-hud-marker--active", callActive);
          el.classList.toggle("vox-hud-marker--speaking", voxSpeaking);
          if (map.getLayer("vox-highlight-layer")) {
            map.setPaintProperty(
              "vox-highlight-layer",
              "fill-extrusion-opacity",
              voxSpeaking ? 0.85 + 0.15 * Math.sin(now / 220) : 1,
            );
          }
```
`index.css`, after `.vox-hud-marker__pin`:

```css
.vox-hud-marker--active .vox-hud-marker__pin {
  box-shadow: 0 0 10px 2px rgba(255, 99, 99, 0.55);
}

.vox-hud-marker--speaking .vox-hud-marker__pin {
  animation: vox-pin-pulse 0.9s ease-out infinite;
}

@keyframes vox-pin-pulse {
  from {
    box-shadow: 0 0 0 0 rgba(255, 99, 99, 0.7);
  }
  to {
    box-shadow: 0 0 0 26px rgba(255, 99, 99, 0);
  }
}
```
- [ ] **Step 4: Android voice + map.** `VoiceSession.kt`: add `fun isVoxSpeaking(): Boolean = audioEngine.isPlaying()`. `MainActivity.kt`: after the `voiceSession` events collector add

```kotlin
    var voxSpeaking by remember { mutableStateOf(false) }
    LaunchedEffect(voiceStatus) {
        while (voiceStatus == VoiceStatus.ACTIVE) {
            voxSpeaking = voiceSession.isVoxSpeaking()
            delay(100)
        }
        voxSpeaking = false
    }
```
(import `kotlinx.coroutines.delay`) and pass `callActive = voiceStatus == VoiceStatus.ACTIVE, voxSpeaking = voxSpeaking` to `MissionMapBackground`. `MissionMap.kt`: add the two params to the composable and controller; hold them in `@Volatile private var callActive/voxSpeaking`, updated by `LaunchedEffect(controller, callActive, voxSpeaking) { controller.setReaction(callActive, voxSpeaking) }`. `OrbitController` takes `private val onFrame: (Long) -> Unit` and `private val speedFactor: () -> Double`; call `onFrame(System.currentTimeMillis())` in `doFrame`, and replace `(if (wantRun) 1.0 else 0.0)` with `(if (wantRun) speedFactor() else 0.0)`. Controller passes `onFrame = { now -> paintReaction(now) }` and `speedFactor = { if (callActive) 0.35 else 1.0 }`. `paintReaction`:

```kotlin
    private fun paintReaction(nowMs: Long) {
        val style = mapRef?.style ?: return
        val you = style.getLayer(YOU_LAYER) as? CircleLayer
        val pulse = if (voxSpeaking) ((nowMs % 900L) / 900f) else 0f
        you?.setProperties(
            PropertyFactory.circleRadius(if (callActive) 7f + 3f else 7f),
            PropertyFactory.circleStrokeWidth(2f + pulse * 10f),
            PropertyFactory.circleStrokeOpacity(1f - pulse),
        )
        (style.getLayer(HIGHLIGHT_LAYER) as? FillExtrusionLayer)?.setProperties(
            PropertyFactory.fillExtrusionOpacity(
                if (voxSpeaking) (0.85f + 0.15f * kotlin.math.sin(nowMs / 220f)) else 1f,
            ),
        )
    }
```
Store the map as `private var mapRef: MapLibreMap? = null` set in `start()` next to `mapDeferred.complete(map)`.
- [ ] **Step 5: Verify.** `cd vox-desktop && npx tsc --noEmit && cargo check --manifest-path src-tauri/Cargo.toml` and `cd vox-android && ./gradlew :app:assembleDebug`: all clean. Run each app, start a call: orbit slows, pin glows; while Vox talks the pin rings pulse and the home building breathes; end the call: everything returns to normal. End the call mid-scene (Task 1 canned scene active): scene remains, orbit stays paused.
- [ ] **Step 6: Commit** in `vox-desktop` and `vox-android`: `git commit -am "feat: map reacts to call and Vox speech"`

---

### Task 5: Agent tools `show_on_map` and `clear_map`

**Files:**
- Create: `vox-core/src/agents/tools/map_scene.rs`
- Modify: `vox-core/src/agents/tools/mod.rs`, `vox-core/src/agents/conversation.rs`, `vox-core/services/api/main.rs`, `vox-core/src/agents/prompts.rs`

**Interfaces:**
- Consumes: `UserEventHub::set_scene`, `MapScene::validate`.
- Produces: `ShowOnMap::new(UserEventHub, Uuid)`, `ClearMap::new(UserEventHub, Uuid)` (rig tools); `ConversationAgent::with_user_events(self, UserEventHub) -> Self`.

- [ ] **Step 1: Create `agents/tools/map_scene.rs`:**

```rust
use crate::{map_scene::MapScene, realtime::UserEventHub};
use rig::tool::Tool;
use serde_json::{Value, json};
use uuid::Uuid;

#[derive(Debug, thiserror::Error)]
pub enum MapToolError {
    #[error("Invalid scene: {0}")]
    Invalid(String),
    #[error("Map is not available")]
    NotConfigured,
}

#[derive(Clone)]
pub struct ShowOnMap {
    hub: Option<UserEventHub>,
    user_id: Uuid,
}

impl ShowOnMap {
    pub fn new(hub: Option<UserEventHub>, user_id: Uuid) -> Self {
        Self { hub, user_id }
    }
}

impl Tool for ShowOnMap {
    const NAME: &'static str = "show_on_map";
    type Args = MapScene;
    type Output = Value;
    type Error = MapToolError;

    fn description(&self) -> String {
        "Show things on the user's 3D map while talking: fly the camera, drop pins, draw animated arcs between places, grow spend columns, highlight buildings. Replaces whatever is on the map. Coordinates are longitude/latitude. Pin kind is place, task or spend. Arcs animate in order using delayMs. Use only coordinates you got from a tool result.".to_owned()
    }

    fn parameters(&self) -> Value {
        let point = json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "lng": { "type": "number" },
                "lat": { "type": "number" }
            },
            "required": ["id", "lng", "lat"]
        });
        json!({
            "type": "object",
            "properties": {
                "camera": {
                    "type": "object",
                    "properties": {
                        "lng": { "type": "number" },
                        "lat": { "type": "number" },
                        "zoom": { "type": "number", "description": "10 to 19; 16 is street level" },
                        "pitch": { "type": "number" },
                        "bearing": { "type": "number" },
                        "durationMs": { "type": "integer" }
                    },
                    "required": ["lng", "lat"]
                },
                "pins": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": { "type": "string" },
                            "lng": { "type": "number" },
                            "lat": { "type": "number" },
                            "label": { "type": "string" },
                            "kind": { "type": "string", "enum": ["place", "task", "spend"] },
                            "spanId": { "type": "string", "description": "Task id, to keep this pin in sync with the task's status" }
                        },
                        "required": ["id", "lng", "lat", "kind"]
                    }
                },
                "arcs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": { "type": "string" },
                            "from": { "type": "array", "items": { "type": "number" }, "description": "[lng, lat]" },
                            "to": { "type": "array", "items": { "type": "number" }, "description": "[lng, lat]" },
                            "label": { "type": "string" },
                            "delayMs": { "type": "integer" }
                        },
                        "required": ["id", "from", "to"]
                    }
                },
                "columns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": { "type": "string" },
                            "lng": { "type": "number" },
                            "lat": { "type": "number" },
                            "value": { "type": "number", "description": "Relative height, for example amount spent" },
                            "label": { "type": "string" }
                        },
                        "required": ["id", "lng", "lat", "value"]
                    }
                },
                "highlights": { "type": "array", "items": point },
                "narrationHint": { "type": "string" }
            }
        })
    }

    async fn call(
        &self,
        _context: &mut rig::prelude::ToolContext,
        args: Self::Args,
    ) -> Result<Self::Output, Self::Error> {
        let hub = self.hub.as_ref().ok_or(MapToolError::NotConfigured)?;
        args.validate().map_err(MapToolError::Invalid)?;
        let scene = hub.set_scene(self.user_id, args);
        Ok(json!({ "shown": true, "rev": scene.rev }))
    }
}

#[derive(Clone)]
pub struct ClearMap {
    hub: Option<UserEventHub>,
    user_id: Uuid,
}

impl ClearMap {
    pub fn new(hub: Option<UserEventHub>, user_id: Uuid) -> Self {
        Self { hub, user_id }
    }
}

impl Tool for ClearMap {
    const NAME: &'static str = "clear_map";
    type Args = Value;
    type Output = Value;
    type Error = MapToolError;

    fn description(&self) -> String {
        "Clear everything shown on the user's map and return the camera to their home view.".to_owned()
    }

    fn parameters(&self) -> Value {
        json!({ "type": "object", "properties": {} })
    }

    async fn call(
        &self,
        _context: &mut rig::prelude::ToolContext,
        _args: Self::Args,
    ) -> Result<Self::Output, Self::Error> {
        let hub = self.hub.as_ref().ok_or(MapToolError::NotConfigured)?;
        hub.set_scene(self.user_id, MapScene::default());
        Ok(json!({ "cleared": true }))
    }
}
```
Note: `MapScene` has `rev` and `#[serde(deny_unknown_fields)]`; the agent never sends `rev` (not in the schema) and `set_scene` overwrites it.

- [ ] **Step 2: Register.** `agents/tools/mod.rs`: add `pub mod map_scene;`.
- [ ] **Step 3: Inject the hub.** In `conversation.rs` add field `user_events: Option<UserEventHub>` to `ConversationAgent` (init `None` in `new`, and in the test constructor near line 565), add `use crate::realtime::UserEventHub;` and:

```rust
    pub fn with_user_events(mut self, hub: UserEventHub) -> Self {
        self.user_events = Some(hub);
        self
    }
```
In `build_agent_and_input` add after the `UpdateAgentMemory` tool:

```rust
            .tool(tools::map_scene::ShowOnMap::new(
                self.user_events.clone(),
                prompt.user_id.0,
            ))
            .tool(tools::map_scene::ClearMap::new(
                self.user_events.clone(),
                prompt.user_id.0,
            ))
```
In `services/api/main.rs` the agent is built before... check the order: `span_notification_hub` and `user_events` are created above the agent (line ~86 is after them); change to `ConversationAgent::with_db(&config, db.clone()).expect("...").with_user_events(user_events.clone())`. If `user_events` is declared after the agent, move its declaration above.
- [ ] **Step 4: Update the allowlist test.** In `governed_tool_surface_tests`, change the expected list to `["clear_map", "get_agent_memory", "library", "show_on_map", "update_agent_memory"]` and the message to `"{channel} must expose only governed tools and the map display tools"`. The agent test constructor has no hub: `ShowOnMap`/`ClearMap` still register (hub `None`), so the names list is unchanged by hub presence.
- [ ] **Step 5: Prompt guidance.** In `agents/prompts.rs`, append to the voice preamble (next to the other voice rules, found via `grep -n "fn preamble_for_channel_and_tts"`): `"When you talk about places, trips or spending, show them on the user's map with show_on_map using coordinates from tool results, then say what the map shows in one short sentence. Call clear_map when asked to clear it."`
- [ ] **Step 6: Verify.** `cd vox-core && cargo check && cargo test governed_tool_surface -- --nocapture` → test passes with the new list. Then call the desktop app, ask "show me my home on the map" with a visit in the data; expected: the agent calls `show_on_map` (visible in Core logs as `Tool called`) and both clients render the scene.
- [ ] **Step 7: Commit** (`vox-core`): `git commit -am "feat: agent tools show_on_map and clear_map"`

---

### Task 6: Visit and spend playback data tool

**Files:**
- Create: `vox-core/src/agents/tools/visits.rs`
- Modify: `vox-core/src/agents/tools/mod.rs`, `conversation.rs` (+ allowlist test)

**Interfaces:**
- Produces: `ListVisits::new(Option<Db>, UserId)` returning `{"visits":[{"id","place","lat","lng","startAt","endAt"}]}` from `spans` rows with `source = 'location'` and `category = 'visit'` (location ingestion writes `data = {place_name, lat, lng}` for those rows, see `vox-core/src/location_ingestion.rs`).

- [ ] **Step 1: Create `tools/visits.rs`:**

```rust
use crate::{
    db::Db,
    domain::spans::SpanQuery,
    identity::UserId,
    storage::spans::SpanRepository,
};
use chrono::{DateTime, Utc};
use rig::tool::Tool;
use serde::Deserialize;
use serde_json::{Value, json};

#[derive(Debug, thiserror::Error)]
pub enum VisitsToolError {
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),
    #[error("Database not configured")]
    NotConfigured,
}

#[derive(Debug, Deserialize)]
pub struct ListVisitsArgs {
    pub from: Option<DateTime<Utc>>,
    pub to: Option<DateTime<Utc>>,
    pub limit: Option<i64>,
}

#[derive(Clone)]
pub struct ListVisits {
    db: Option<Db>,
    user_id: UserId,
}

impl ListVisits {
    pub fn new(db: Option<Db>, user_id: UserId) -> Self {
        Self { db, user_id }
    }
}

impl Tool for ListVisits {
    const NAME: &'static str = "list_visits";
    type Args = ListVisitsArgs;
    type Output = Value;
    type Error = VisitsToolError;

    fn description(&self) -> String {
        "List places the user visited (name, coordinates, time) from their location history. Use the coordinates with show_on_map.".to_owned()
    }

    fn parameters(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "from": { "type": "string", "description": "RFC 3339 start of range" },
                "to": { "type": "string", "description": "RFC 3339 end of range" },
                "limit": { "type": "integer", "description": "Max visits, default 30, max 50" }
            }
        })
    }

    async fn call(
        &self,
        _context: &mut rig::prelude::ToolContext,
        args: Self::Args,
    ) -> Result<Self::Output, Self::Error> {
        let db = self.db.as_ref().ok_or(VisitsToolError::NotConfigured)?;
        let repo = SpanRepository::new(db.pool().clone());
        let spans = repo
            .list(
                self.user_id.0,
                &SpanQuery {
                    from: args.from,
                    to: args.to,
                    limit: Some(500),
                    ..Default::default()
                },
            )
            .await?;
        let visits: Vec<Value> = spans
            .into_iter()
            .filter(|s| s.source == "location" && s.category == "visit")
            .filter_map(|s| {
                let lat = s.data.get("lat")?.as_f64()?;
                let lng = s.data.get("lng")?.as_f64()?;
                Some(json!({
                    "id": s.id,
                    "place": s.title,
                    "lat": lat,
                    "lng": lng,
                    "startAt": s.start_at,
                    "endAt": s.end_at,
                }))
            })
            .take(args.limit.unwrap_or(30).clamp(1, 50) as usize)
            .collect();
        Ok(json!({ "visits": visits }))
    }
}
```
If `SpanQuery` does not derive `Default`, build it with all fields spelled out (`collection_id: None, schema_id: None, status: None, unscheduled: false`); `cargo check` will say.
- [ ] **Step 2: Register.** `tools/mod.rs`: `pub mod visits;`. `conversation.rs`: `.tool(tools::visits::ListVisits::new(self.db.clone(), prompt.user_id))`. Allowlist test list becomes `["clear_map", "get_agent_memory", "library", "list_visits", "show_on_map", "update_agent_memory"]`.
- [ ] **Step 3: Prompt.** Add to the Task 5 voice guidance: `"For trips or where the user has been, call list_visits, then show_on_map with the visits as pins and arcs between consecutive visits using increasing delayMs (about 800 per leg). For spending, use query_user_data results and put spend columns on matching visit coordinates; if no coordinates exist for a spend, say so instead of guessing."`
- [ ] **Step 4: Verify.** `cargo check && cargo test governed_tool_surface`. Run the stack and ask Vox "show me where I went this week": expect a `list_visits` then `show_on_map` call, pins appear, arcs draw one after another. With no visit data the agent should say so and show nothing.
- [ ] **Step 5: Commit** (`vox-core`): `git commit -am "feat: list_visits tool for map playback"`

---

### Task 7: Live task pins

**Files:**
- Modify: `vox-core/src/realtime.rs`, `vox-core/src/application/spans.rs`

**Interfaces:**
- Produces: `UserEventHub::sync_task_pin(&self, user_id: Uuid, span_id: Uuid, status: Option<&str>)`: finds pins whose `span_id` matches in the user's current scene; `Some(status)` sets their `state`, `None` removes them; republishes through `set_scene` only if something changed.
- Consumes: `show_on_map` pins carrying `spanId` (Task 5).

- [ ] **Step 1: Add to `impl UserEventHub` in `realtime.rs`:**

```rust
    pub fn sync_task_pin(&self, user_id: Uuid, span_id: Uuid, status: Option<&str>) {
        let updated = {
            let scenes = self.scenes.lock().expect("map scene lock poisoned");
            let Some((_, scene)) = scenes.get(&user_id) else { return };
            if !scene.pins.iter().any(|p| p.span_id == Some(span_id)) {
                return;
            }
            let mut next = scene.clone();
            match status {
                Some(status) => {
                    for pin in next.pins.iter_mut().filter(|p| p.span_id == Some(span_id)) {
                        pin.state = Some(status.to_owned());
                    }
                }
                None => next.pins.retain(|p| p.span_id != Some(span_id)),
            }
            next
        };
        self.set_scene(user_id, updated);
    }
```
- [ ] **Step 2: Call it from `SpanService`.** In `application/spans.rs`, in `update_span` next to the existing `self.notify(actor.user_id, "span_updated", span.id);` add `self.user_events.sync_task_pin(actor.user_id, span.id, serde_json::to_value(&span.status).ok().as_ref().and_then(|v| v.as_str()));`, and in `delete_span` next to `span_deleted` add `self.user_events.sync_task_pin(actor.user_id, id, None);`.
- [ ] **Step 3: Clients show state.** Add a state suffix to the pin label in both renderers: desktop `label: p.state ? `${p.label ?? ""} · ${p.state}` : (p.label ?? "")`; Android `addStringProperty("label", listOfNotNull(it.label, it.state).joinToString(" · "))`.
- [ ] **Step 4: Verify.** `cargo check` in `vox-core`, `npx tsc --noEmit` in desktop, `assembleDebug` on Android. POST a scene with a pin `{"id":"t","lng":..,"lat":..,"kind":"task","label":"Cab","spanId":"<existing span id>"}`; update that span's status through the app: the pin label gains `· done` on both clients without any new POST. Delete the span: pin disappears. Spans created by the worker process do not pass through `SpanService` in the API process, so they will not update pins until the worker's DB-polling loop in `services/api/main.rs` (the `span_created` loop) is extended; out of scope here.
- [ ] **Step 5: Commit** in all three repos: `git commit -am "feat: live task pins on the map"`

---

### Task 8: Cleanup and docs

**Files:**
- Modify: `vox-core/services/api/router.rs`, `routes/map_scene.rs`
- Delete: empty dirs `vox-desktop/src/features/{pulse,spaces,spans}`, `vox-desktop/src/components/spaces` (only if still empty)
- Modify: `vox-desktop/README.md`, `vox-desktop/src/hooks/use-mission-map.ts`

- [ ] **Step 1: Remove the temporary POST.** Delete `post_map_scene` and its import; the route becomes `.route("/v1/me/map/scene", get(get_map_scene))`. `cargo check` clean.
- [ ] **Step 2: Remove empty directories after verifying.** Run `find vox-desktop/src/features vox-desktop/src/components/spaces -type f` → expect no output; then `rmdir` each empty directory.
- [ ] **Step 3: Remove unused map hook returns.** Run `grep -rn "locationSource\|permissionDenied\|relocate\|\.location\b" vox-desktop/src --include=*.tsx --include=*.ts | grep -v use-mission-map`. For every returned field with no consumer outside the hook (the only consumer is `home-shell.tsx`, which uses `mapNode, mapReady, mapError`), delete the state, setters, `relocateRef`, `resolveDeviceLocation` result plumbing and the `ResolvedLocation` type; keep `applyPosition` and the location resolve it needs.
- [ ] **Step 4: Check for orphans.** `grep -rn "highlightBuildingAt" vox-desktop vox-android --include=*.ts --include=*.tsx --include=*.kt` → expect no output. In `vox-desktop`: `npx tsc --noEmit && npm run lint`. In `vox-android`: `./gradlew :app:assembleDebug`.
- [ ] **Step 5: Docs.** In `vox-desktop/README.md` "Map home" add: "Vox can drive the map: scenes arrive as `map_scene` frames on the live socket (`GET /v1/me/map/scene` on start). See `docs/superpowers/specs/2026-10-04-map-scenes-design.md`." Add the one-line frame description to `vox-core/contracts/device-protocol.md` section 2 or a new short section on the user event socket.
- [ ] **Step 6: Final run.** Repeat the Task 2 and Task 3 visual checks via voice: "show me where I went this week", then "clear the map". Expected on both clients: pins and arcs appear, map returns home when cleared.
- [ ] **Step 7: Commit** in each repo: `git commit -am "chore: remove scene scaffolding and dead map code"`

---

## Self-review

- **Spec coverage:** contract and Core store (T1); desktop and Android source + renderer (T2, T3); voice reactions (T4); agent tools (T5); spend and travel playback (T5 prompt, T6); task pins (T7); dead code removal (T8). Redis and per-id diffing deviations are stated at the top.
- **Placeholders:** none. Two edits depend on `cargo check` feedback and say so (`SpanQuery: Default`, `user_events` declaration order).
- **Type consistency:** `MapScene`, `rev`, `delayMs`, `spanId`, `kind` strings match across Rust, TypeScript, Kotlin; `setHighlights(map, points)` is used by both renderers; `ShowOnMap::new(Option<UserEventHub>, Uuid)` matches its call site.
- **Known limits:** scenes are lost on API restart and expire after 30 minutes; worker-originated span changes do not move task pins; `search_places` is deliberately not exposed to the conversation agent.
