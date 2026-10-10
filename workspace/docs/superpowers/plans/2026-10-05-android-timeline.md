# Android Native Foundation + Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Native Android Timeline (Day/Week/Month, span sheet, collections, live updates) on a reusable native foundation, matching desktop behaviour and API.

**Architecture:** `VoxApi` typed POST client over `VoxHttp`; one process-wide `LiveSocket` shared by the map scene and Timeline; pure-Kotlin ports of desktop `span-layout`/`span-format`; a `TimelineViewModel` (StateFlow) driving Compose screens hosted as a full-screen layer over the map, switched by a `Destination` in the bottom nav.

**Tech Stack:** Kotlin, Jetpack Compose (material3, BOM 2026.09), `lifecycle-viewmodel-compose`, OkHttp, kotlinx.serialization, `java.time`.

**Spec:** `docs/superpowers/specs/2026-10-05-android-timeline-design.md`

## Global Constraints

- Same HTTP API and request bodies as desktop `spansApi` (spec "API" section); snake_case JSON; bearer token from `AuthManager`.
- No new test files and no code comments in new code (project preference). Each task ends with a build check; Task 8 is the emulator verification.
- Week starts Sunday; Day default; polling 15 s only while the Timeline is on screen.
- Update body never includes `expected_version`; `start_at`/`end_at` are sent as explicit JSON `null` when cleared (Core distinguishes null from absent).
- Package root `in.voxagent.mobile` (Kotlin: backticked `in`). Paths below are relative to `vox-android/app/src/main/java/in/voxagent/mobile/`.
- Commits are left to you; this plan does not commit.

## Review Focus

- Spans overlapping midnight, spanning several days, or exactly 24 h: must appear in the all-day row, not as a broken block (Task 2 layout port, Task 8 check).
- Empty ranges, offline, 401 and server error: Timeline shows an error bar with Retry, never a blank crash (Task 3, Task 8).
- Clearing a span's end time: sends JSON `null`, not omitted (Task 5).
- Google Calendar spans (`source == "google_calendar"`) must keep title/time/status read-only (Task 5).
- DST day boundaries and non-UTC phones: day math uses `LocalDate` + `ZoneId.systemDefault()`, never `+24h` (Task 2).
- Switching Day/Week/Month then back must keep the anchor rules (Sunday week start, month first) (Task 3).

---

### Task 1: Foundation (API client, live socket, kit, nav destinations)

**Files:**
- Create: `net/VoxApi.kt`, `net/LiveSocket.kt`, `ui/kit/Kit.kt`
- Modify: `map/scene/SceneSource.kt`, `map/MissionMap.kt`, `ui/PhoneVerificationFlow.kt`, `ui/VoxComponents.kt`, `ui/VoxBottomNav.kt`, `app/build.gradle.kts` (path `vox-android/app/build.gradle.kts`)

**Interfaces:**
- Produces: `VoxJson`, `ApiException(status, message)`, `VoxApi.post(path, body, resultSerializer, token)`, `VoxApi.postUnit(path, body, token)`; `LiveEvent(type, payload)`, `LiveHub.get(token): LiveSocket`, `LiveSocket.events: SharedFlow<LiveEvent>`, types `"live_reconnected"`; kit composables `VoxSegmented`, `VoxChip`, `VoxErrorBar`, `VoxEmpty`; `voxFieldColors()`; `enum Destination { Home, Timeline }`; `VoxBottomNav(destination, onDestination, ...)`.

- [ ] **Step 1: Dependency.** In `app/build.gradle.kts` add after `lifecycle-runtime-ktx`: `implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.11.0")`.

- [ ] **Step 2: `net/VoxApi.kt`**

```kotlin
package `in`.voxagent.mobile.net

import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

val VoxJson = Json {
    ignoreUnknownKeys = true
    coerceInputValues = true
}

class ApiException(val status: Int, message: String) : Exception(message)

object VoxApi {
    suspend fun <T> post(
        path: String,
        body: JsonObject,
        result: DeserializationStrategy<T>,
        token: String,
    ): T = VoxJson.decodeFromString(result, send(path, body, token))

    suspend fun postUnit(path: String, body: JsonObject = JsonObject(emptyMap()), token: String) {
        send(path, body, token)
    }

    private suspend fun send(path: String, body: JsonObject, token: String): String =
        try {
            VoxHttp.postJson(path, body.toString(), token)
        } catch (e: VoxHttpException) {
            throw ApiException(e.statusCode, errorMessage(e))
        }

    private fun errorMessage(e: VoxHttpException): String =
        runCatching {
            val obj = VoxJson.parseToJsonElement(e.responseBody).jsonObject
            (obj["error"] ?: obj["message"])?.jsonPrimitive?.content
        }.getOrNull() ?: "Request failed (${e.statusCode})"
}
```

- [ ] **Step 3: `net/LiveSocket.kt`**

```kotlin
package `in`.voxagent.mobile.net

import `in`.voxagent.mobile.BuildConfig
import kotlinx.coroutines.CompletableDeferred
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
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit

data class LiveEvent(val type: String, val payload: JsonObject)

object LiveHub {
    private var socket: LiveSocket? = null

    @Synchronized
    fun get(token: () -> String?): LiveSocket =
        socket ?: LiveSocket(token).also { socket = it }
}

class LiveSocket(private val token: () -> String?) {
    private val client = VoxHttp.client.newBuilder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .build()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val _events = MutableSharedFlow<LiveEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<LiveEvent> = _events.asSharedFlow()
    private var job: Job? = null

    @Synchronized
    fun start() {
        if (job != null) return
        job = scope.launch {
            var everOpened = false
            while (isActive) {
                val bearer = token()
                if (bearer != null) {
                    val opened = connect(bearer, announceReconnect = everOpened)
                    everOpened = everOpened || opened
                }
                delay(RETRY_MS)
            }
        }
    }

    private suspend fun connect(bearer: String, announceReconnect: Boolean): Boolean {
        val closed = CompletableDeferred<Unit>()
        var opened = false
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
        val ws = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                opened = true
                if (announceReconnect) _events.tryEmit(LiveEvent("live_reconnected", JsonObject(emptyMap())))
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching {
                    val frame = VoxJson.parseToJsonElement(text).jsonObject
                    val type = frame["type"]?.jsonPrimitive?.content
                    if (type != null) _events.tryEmit(LiveEvent(type, frame))
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                closed.complete(Unit)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                closed.complete(Unit)
            }
        })
        try {
            closed.await()
        } finally {
            ws.cancel()
        }
        return opened
    }

    private companion object {
        const val RETRY_MS = 5_000L
    }
}
```

- [ ] **Step 4: Rewrite `map/scene/SceneSource.kt` on top of `LiveSocket`** (replace the whole file):

```kotlin
package `in`.voxagent.mobile.map.scene

import `in`.voxagent.mobile.net.LiveSocket
import `in`.voxagent.mobile.net.VoxHttp
import `in`.voxagent.mobile.net.VoxJson
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
import kotlinx.serialization.json.decodeFromJsonElement

class SceneSource(private val token: () -> String?, private val live: LiveSocket) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val _scenes = MutableSharedFlow<MapScene>(replay = 1, extraBufferCapacity = 8)
    val scenes: SharedFlow<MapScene> = _scenes.asSharedFlow()
    private var job: Job? = null

    fun start() {
        if (job != null) return
        live.start()
        job = scope.launch {
            launch {
                live.events.collect { event ->
                    when (event.type) {
                        "map_scene" -> runCatching {
                            _scenes.tryEmit(VoxJson.decodeFromJsonElement<MapScene>(event.payload.getValue("scene")))
                        }
                        "live_reconnected" -> refresh()
                    }
                }
            }
            while (isActive && !refresh()) delay(RETRY_MS)
        }
    }

    fun stop() {
        job?.cancel()
        job = null
    }

    private suspend fun refresh(): Boolean {
        val bearer = token() ?: return false
        return runCatching {
            val body = VoxHttp.getJson("/v1/me/map/scene", bearer)
            _scenes.emit(VoxJson.decodeFromString<MapScene>(body))
        }.isSuccess
    }

    private companion object {
        const val RETRY_MS = 5_000L
    }
}
```
In `map/MissionMap.kt` change `private val sceneSource = SceneSource(token)` to `private val sceneSource = SceneSource(token, LiveHub.get(token))` and add `import in.voxagent.mobile.net.LiveHub` (backticked `in`).

- [ ] **Step 5: Shared field colours.** Cut `private fun darkFieldColors()` from `ui/PhoneVerificationFlow.kt` and paste into `ui/VoxComponents.kt` as `@Composable fun voxFieldColors() = OutlinedTextFieldDefaults.colors(...)` (same body; add imports `OutlinedTextFieldDefaults`, `Iron`, `SmokeDark` if missing); in the phone flow replace both `darkFieldColors()` calls with `voxFieldColors()` and drop its unused imports.

- [ ] **Step 6: `ui/kit/Kit.kt`**

```kotlin
package `in`.voxagent.mobile.ui.kit

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.border
import `in`.voxagent.mobile.ui.theme.BorderSubtle
import `in`.voxagent.mobile.ui.theme.CoralPulse
import `in`.voxagent.mobile.ui.theme.GraphiteDark
import `in`.voxagent.mobile.ui.theme.Mist
import `in`.voxagent.mobile.ui.theme.Obsidian
import `in`.voxagent.mobile.ui.theme.SmokeDark

@Composable
fun <T> VoxSegmented(
    options: List<Pair<T, String>>,
    selected: T,
    onSelect: (T) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .height(36.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(Obsidian)
            .border(BorderStroke(1.dp, BorderSubtle), RoundedCornerShape(10.dp))
            .padding(2.dp),
    ) {
        options.forEach { (value, label) ->
            val on = value == selected
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(32.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(if (on) BorderSubtle else Color.Transparent)
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                    ) { onSelect(value) },
                contentAlignment = Alignment.Center,
            ) {
                Text(label, color = if (on) Mist else GraphiteDark, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            }
        }
    }
}

@Composable
fun VoxChip(text: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(50))
            .background(if (selected) BorderSubtle else Color.Transparent)
            .border(BorderStroke(1.dp, if (selected) Mist.copy(alpha = 0.5f) else BorderSubtle), RoundedCornerShape(50))
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 6.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = if (selected) Mist else GraphiteDark, fontSize = 12.sp)
    }
}

@Composable
fun VoxErrorBar(message: String, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(Obsidian)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(message, color = CoralPulse, fontSize = 12.sp, modifier = Modifier.weight(1f))
        Text(
            "Retry",
            color = Mist,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier
                .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onRetry)
                .padding(start = 12.dp),
        )
    }
}

@Composable
fun VoxEmpty(title: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(title, color = SmokeDark, fontSize = 13.sp, textAlign = TextAlign.Center, fontFamily = FontFamily.Monospace)
    }
}
```

- [ ] **Step 7: Nav destinations in `ui/VoxBottomNav.kt`.** Add above `TalkState`: `enum class Destination { Home, Timeline }`. Add params `destination: Destination = Destination.Home, onDestination: (Destination) -> Unit = {},` to `VoxBottomNav`. In the left pill `Row`, replace the single logo `Box` with two buttons:

```kotlin
                NavDestinationButton(
                    selected = destination == Destination.Home,
                    description = "Home",
                    onClick = { onDestination(Destination.Home) },
                ) { tint ->
                    VoxLogo(size = 24.dp, color = tint, animated = true, modifier = Modifier.aspectRatio(1f))
                }
                NavDestinationButton(
                    selected = destination == Destination.Timeline,
                    description = "Timeline",
                    onClick = { onDestination(Destination.Timeline) },
                ) { tint -> CalendarIcon(tint = tint, modifier = Modifier.size(22.dp)) }
```
and add at file end:

```kotlin
@Composable
private fun NavDestinationButton(
    selected: Boolean,
    description: String,
    onClick: () -> Unit,
    content: @Composable (Color) -> Unit,
) {
    val tint = if (selected) PureWhite else PureWhite.copy(alpha = 0.38f)
    Box(
        modifier = Modifier
            .size(40.dp)
            .clip(CircleShape)
            .semantics { contentDescription = description }
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { content(tint) }
}

@Composable
fun CalendarIcon(tint: Color, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        val w = size.width
        val h = size.height
        val stroke = Stroke(width = w * 0.09f, cap = StrokeCap.Round, join = StrokeJoin.Round)
        drawRoundRect(tint, topLeft = Offset(w * 0.1f, h * 0.18f), size = Size(w * 0.8f, h * 0.72f), cornerRadius = CornerRadius(w * 0.14f), style = stroke)
        drawLine(tint, Offset(w * 0.1f, h * 0.42f), Offset(w * 0.9f, h * 0.42f), strokeWidth = w * 0.09f, cap = StrokeCap.Round)
        drawLine(tint, Offset(w * 0.32f, h * 0.06f), Offset(w * 0.32f, h * 0.28f), strokeWidth = w * 0.09f, cap = StrokeCap.Round)
        drawLine(tint, Offset(w * 0.68f, h * 0.06f), Offset(w * 0.68f, h * 0.28f), strokeWidth = w * 0.09f, cap = StrokeCap.Round)
    }
}
```
Add imports: `androidx.compose.foundation.Canvas`, `androidx.compose.ui.geometry.{Offset,Size,CornerRadius}`, `androidx.compose.ui.graphics.{StrokeCap,StrokeJoin}`, `androidx.compose.ui.graphics.drawscope.Stroke`.

- [ ] **Step 8: Verify.** Run `cd vox-android && ./gradlew :app:assembleDebug --console=plain -q 2>&1 | grep -E "^e:|FAILED"` → expect no output. Map scene delivery is re-checked in Task 8.

---

### Task 2: Models, API, formatting, layout (pure logic)

**Files:** Create `spans/SpanModels.kt`, `spans/SpansApi.kt`, `spans/SpanFormat.kt`, `spans/SpanLayout.kt`

**Interfaces:**
- Produces: `Span`, `SpanCollection`, `SpanStatus`, `ExecutionType`; `SpansApi.{getSpans,createSpan,updateSpan,deleteSpan,getCollections,setSpanCollection}`; `CategoryStyle`, `categoryStyle(category, schemaColorToken)`, `formatTime(ms)`, `formatAmount(span)`; `PlacedSpan`, `layoutDay(spans, day)`, `layoutAllDay(spans, days)`, `monthGridDays(anchor)`, `weekStart(date)`, `dayStartMs(day)`, `spansOnDay(spans, day)`, `zone`.

- [ ] **Step 1: `spans/SpanModels.kt`**

```kotlin
package `in`.voxagent.mobile.spans

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import java.time.OffsetDateTime

@Serializable
enum class SpanStatus {
    @SerialName("planned") Planned,
    @SerialName("active") Active,
    @SerialName("waiting_user") WaitingUser,
    @SerialName("done") Done,
    @SerialName("failed") Failed,
    @SerialName("cancelled") Cancelled;

    val wire: String get() = when (this) {
        Planned -> "planned"
        Active -> "active"
        WaitingUser -> "waiting_user"
        Done -> "done"
        Failed -> "failed"
        Cancelled -> "cancelled"
    }
    val label: String get() = wire.replace('_', ' ')
}

@Serializable
enum class ExecutionType {
    @SerialName("autonomous") Autonomous,
    @SerialName("interactive") Interactive,
    @SerialName("manual_human") ManualHuman;

    val wire: String get() = when (this) {
        Autonomous -> "autonomous"
        Interactive -> "interactive"
        ManualHuman -> "manual_human"
    }
}

@Serializable
data class Span(
    val id: String,
    @SerialName("parent_id") val parentId: String? = null,
    val title: String,
    val notes: String = "",
    val category: String = "",
    val source: String = "",
    val status: SpanStatus = SpanStatus.Planned,
    @SerialName("start_at") val startAt: String? = null,
    @SerialName("end_at") val endAt: String? = null,
    @SerialName("execution_type") val executionType: ExecutionType? = null,
    val data: JsonElement? = null,
    @SerialName("schema_color_token") val schemaColorToken: Int? = null,
    @SerialName("schema_icon_token") val schemaIconToken: Int? = null,
    @SerialName("collection_ids") val collectionIds: List<String> = emptyList(),
    val version: Int = 0,
) {
    val startMs: Long? get() = startAt?.let { runCatching { OffsetDateTime.parse(it).toInstant().toEpochMilli() }.getOrNull() }
    val endMs: Long? get() = endAt?.let { runCatching { OffsetDateTime.parse(it).toInstant().toEpochMilli() }.getOrNull() }
    val amount: Double? get() = ((data as? JsonObject)?.get("amount") as? JsonPrimitive)?.takeIf { !it.isString }?.doubleOrNull
    val currency: String get() = ((data as? JsonObject)?.get("currency") as? JsonPrimitive)?.contentOrNull ?: "INR"
}

@Serializable
data class SpanCollection(
    val id: String,
    val name: String,
    val kind: String = "custom",
    val status: String = "",
    @SerialName("starts_at") val startsAt: String? = null,
    @SerialName("ends_at") val endsAt: String? = null,
    @SerialName("span_count") val spanCount: Int = 0,
    val version: Int = 0,
)
```

- [ ] **Step 2: `spans/SpansApi.kt`**

```kotlin
package `in`.voxagent.mobile.spans

import `in`.voxagent.mobile.net.VoxApi
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.time.Instant

object SpansApi {
    suspend fun getSpans(token: String, from: Instant, to: Instant, collectionId: String?): List<Span> =
        VoxApi.post(
            "/v1/spans/list",
            buildJsonObject {
                put("from", from.toString())
                put("to", to.toString())
                if (collectionId != null) put("collection_id", collectionId)
            },
            ListSerializer(Span.serializer()),
            token,
        )

    suspend fun createSpan(token: String, body: JsonObject): Span =
        VoxApi.post("/v1/spans", body, Span.serializer(), token)

    suspend fun updateSpan(token: String, id: String, body: JsonObject): Span =
        VoxApi.post("/v1/spans/$id/update", body, Span.serializer(), token)

    suspend fun deleteSpan(token: String, id: String) =
        VoxApi.postUnit("/v1/spans/$id/delete", token = token)

    suspend fun getCollections(token: String): List<SpanCollection> =
        VoxApi.post("/v1/collections/list", JsonObject(emptyMap()), ListSerializer(SpanCollection.serializer()), token)

    suspend fun setSpanCollection(token: String, collectionId: String, spanId: String, member: Boolean) =
        VoxApi.postUnit("/v1/collections/$collectionId/spans/$spanId/${if (member) "add" else "remove"}", token = token)
}
```

- [ ] **Step 3: `spans/SpanFormat.kt`**

```kotlin
package `in`.voxagent.mobile.spans

import androidx.compose.ui.graphics.Color
import java.text.NumberFormat
import java.time.Instant
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Currency
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin

data class CategoryStyle(val bg: Color, val border: Color, val dot: Color, val subtext: Color)

private fun rgba(r: Int, g: Int, b: Int, a: Float) = Color(r / 255f, g / 255f, b / 255f, a)
private fun hex(value: Long) = Color(0xFF000000 or value)

private fun style(bg: Color, border: Color, dot: Color, sub: Color) = CategoryStyle(bg, border, dot, sub)

private val Violet = style(rgba(35, 25, 72, .88f), rgba(139, 92, 246, .35f), hex(0xa78bfa), rgba(196, 181, 253, .75f))
private val Blue = style(rgba(20, 38, 70, .88f), rgba(59, 130, 246, .35f), hex(0x60a5fa), rgba(147, 197, 253, .75f))
private val Green = style(rgba(13, 48, 30, .88f), rgba(16, 185, 129, .35f), hex(0x34d399), rgba(110, 231, 183, .75f))
private val Rose = style(rgba(60, 20, 38, .88f), rgba(244, 63, 94, .35f), hex(0xfb7185), rgba(253, 164, 175, .75f))
private val Amber = style(rgba(58, 32, 10, .88f), rgba(245, 158, 11, .35f), hex(0xfbbf24), rgba(253, 230, 138, .75f))
private val Orange = style(rgba(56, 26, 14, .88f), rgba(249, 115, 22, .35f), hex(0xfb923c), rgba(254, 215, 170, .75f))
private val Purple = style(rgba(42, 18, 76, .88f), rgba(168, 85, 247, .38f), hex(0xc084fc), rgba(233, 213, 255, .75f))
private val Slate = style(rgba(24, 26, 32, .9f), rgba(148, 163, 184, .25f), hex(0x94a3b8), rgba(203, 213, 225, .75f))
private val Fallback = style(rgba(26, 30, 42, .88f), rgba(100, 116, 139, .3f), hex(0x94a3b8), rgba(255, 255, 255, .65f))

private val CATEGORY_STYLES = mapOf(
    "meeting" to Violet, "call" to Violet, "reminder" to Violet,
    "commute" to Blue, "travel" to Blue, "driving" to Blue,
    "cycling" to Green, "ride" to Green, "running" to Green, "walking" to Green,
    "visit" to Rose, "appointment" to Rose,
    "expense" to Amber, "payment" to Amber, "delivery" to Amber,
    "meal" to Orange, "food" to Orange,
    "game" to Purple, "gaming" to Purple,
    "todo" to Slate,
)

private fun oklch(l: Double, c: Double, h: Double, alpha: Float): Color {
    val a = c * cos(Math.toRadians(h))
    val b = c * sin(Math.toRadians(h))
    val l_ = l + 0.3963377774 * a + 0.2158037573 * b
    val m_ = l - 0.1055613458 * a - 0.0638541728 * b
    val s_ = l - 0.0894841775 * a - 1.2914855480 * b
    val l3 = l_ * l_ * l_
    val m3 = m_ * m_ * m_
    val s3 = s_ * s_ * s_
    fun enc(x: Double): Float {
        val v = x.coerceIn(0.0, 1.0)
        return (if (v <= 0.0031308) 12.92 * v else 1.055 * v.pow(1 / 2.4) - 0.055).toFloat()
    }
    return Color(
        enc(4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3),
        enc(-1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3),
        enc(-0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3),
        alpha,
    )
}

private fun schemaStyle(token: Int): CategoryStyle {
    val t = if (token in 0..23) token else 0
    val hue = ((20 + 15 * t) % 360).toDouble()
    return CategoryStyle(
        bg = oklch(0.22, 0.14, hue, .9f),
        border = oklch(0.72, 0.14, hue, .35f),
        dot = oklch(0.72, 0.14, hue, 1f),
        subtext = oklch(0.72, 0.14, hue, .75f),
    )
}

fun categoryStyle(category: String, schemaColorToken: Int?): CategoryStyle =
    if (schemaColorToken != null) schemaStyle(schemaColorToken)
    else CATEGORY_STYLES[category.lowercase()] ?: Fallback

private val timeFormat = DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT).withZone(zone)

fun formatTime(ms: Long?): String = if (ms == null) "" else timeFormat.format(Instant.ofEpochMilli(ms))

fun formatMoney(amount: Double, currency: String = "INR"): String =
    runCatching {
        NumberFormat.getCurrencyInstance().apply {
            this.currency = Currency.getInstance(currency)
            maximumFractionDigits = 0
        }.format(amount)
    }.getOrDefault("$amount $currency")

fun formatAmount(span: Span): String? = span.amount?.let { formatMoney(it, span.currency) }
```

- [ ] **Step 4: `spans/SpanLayout.kt`** (1:1 port of `lib/span-layout.ts`)

```kotlin
package `in`.voxagent.mobile.spans

import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.ChronoUnit

private const val MINUTE = 60_000L
private const val DAY_MINUTES = 24 * 60
const val MIN_BLOCK_MINUTES = 25.0
private const val CHILD_HEADER_MINUTES = 22.0

val zone: ZoneId get() = ZoneId.systemDefault()

data class PlacedSpan(
    val span: Span,
    val top: Double,
    val height: Double,
    val left: Double,
    val width: Double,
    val depth: Int,
    val instant: Boolean,
)

private class Node(val span: Span, var start: Double, var end: Double, val instant: Boolean) {
    val children = mutableListOf<Node>()
}

fun dayStartMs(day: LocalDate): Long = day.atStartOfDay(zone).toInstant().toEpochMilli()

fun weekStart(date: LocalDate): LocalDate = date.minusDays((date.dayOfWeek.value % 7).toLong())

private fun bounds(span: Span): Pair<Long, Long>? {
    val start = span.startMs ?: return null
    val end = span.endMs ?: start
    return start to maxOf(start, end)
}

fun isAllDay(span: Span): Boolean {
    val b = bounds(span) ?: return false
    return b.second - b.first >= DAY_MINUTES * MINUTE
}

fun spansOnDay(spans: List<Span>, day: LocalDate): List<Span> {
    val start = dayStartMs(day)
    val end = dayStartMs(day.plusDays(1))
    return spans.filter { span ->
        val b = bounds(span) ?: return@filter false
        if (b.first == b.second) b.first in start until end else b.second > start && b.first < end
    }.sortedWith(compareByDescending<Span> { isAllDay(it) }.thenBy { it.startMs ?: 0L })
}

private fun pack(nodes: List<Node>, left: Double, width: Double, depth: Int, out: MutableList<PlacedSpan>) {
    val instants = nodes.filter { it.instant }
    val durations = nodes.filter { !it.instant }
    val sorted = durations.sortedWith(compareBy<Node> { it.start }.thenByDescending { it.end })
    var cluster = mutableListOf<Pair<Node, Int>>()
    var columnEnds = mutableListOf<Double>()
    var clusterEnd = Double.NEGATIVE_INFINITY

    fun flush() {
        val cols = columnEnds.size
        for ((node, col) in cluster) {
            val w = width / cols
            val l = left + col * w
            out += PlacedSpan(node.span, node.start, node.end - node.start, l, w, depth, false)
            for (child in node.children) {
                child.start = maxOf(child.start, node.start + CHILD_HEADER_MINUTES)
                child.end = maxOf(child.end, child.start + MIN_BLOCK_MINUTES)
            }
            pack(node.children, l, w, depth + 1, out)
        }
        cluster = mutableListOf()
        columnEnds = mutableListOf()
    }

    for (node in sorted) {
        if (node.start >= clusterEnd) {
            flush()
            clusterEnd = Double.NEGATIVE_INFINITY
        }
        var col = columnEnds.indexOfFirst { it <= node.start }
        if (col == -1) {
            col = columnEnds.size
            columnEnds.add(node.end)
        } else {
            columnEnds[col] = node.end
        }
        cluster.add(node to col)
        clusterEnd = maxOf(clusterEnd, node.end)
    }
    flush()

    for (node in instants) {
        out += PlacedSpan(node.span, node.start, node.end - node.start, left, width, depth, true)
        pack(node.children, left, width, depth + 1, out)
    }
}

fun layoutDay(spans: List<Span>, day: LocalDate): List<PlacedSpan> {
    val dayStart = dayStartMs(day)
    val dayEnd = dayStartMs(day.plusDays(1))
    val nodes = LinkedHashMap<String, Node>()
    for (span in spans) {
        val b = bounds(span) ?: continue
        if (isAllDay(span)) continue
        val (start, end) = b
        val instant = end == start
        val outside = if (instant) start < dayStart || start >= dayEnd else end <= dayStart || start >= dayEnd
        if (outside) continue
        val s = (maxOf(start, dayStart) - dayStart).toDouble() / MINUTE
        val e = (minOf(end, dayEnd) - dayStart).toDouble() / MINUTE
        val top = minOf(s, DAY_MINUTES - MIN_BLOCK_MINUTES)
        nodes[span.id] = Node(span, top, maxOf(e, top + MIN_BLOCK_MINUTES), instant)
    }
    val roots = mutableListOf<Node>()
    for (node in nodes.values) {
        val parent = node.span.parentId?.let { nodes[it] }
        if (parent != null && parent !== node) parent.children.add(node) else roots.add(node)
    }
    val out = mutableListOf<PlacedSpan>()
    pack(roots, 0.0, 1.0, 0, out)
    return out
}

data class AllDayRow(val span: Span, val startCol: Int, val endCol: Int, val row: Int)

fun layoutAllDay(spans: List<Span>, days: List<LocalDate>): List<AllDayRow> {
    if (days.isEmpty()) return emptyList()
    val first = dayStartMs(days[0])
    val dayMs = DAY_MINUTES * MINUTE
    val rowEnds = mutableListOf<Int>()
    val out = mutableListOf<AllDayRow>()
    val items = spans.filter(::isAllDay).mapNotNull { span ->
        val (start, end) = bounds(span)!!
        val startCol = maxOf(0L, Math.floorDiv(start - first, dayMs)).toInt()
        val endCol = minOf((days.size - 1).toLong(), Math.floorDiv(end - 1 - first, dayMs)).toInt()
        if (endCol >= 0 && startCol < days.size && startCol <= endCol) Triple(span, startCol, endCol) else null
    }.sortedBy { it.second }
    for ((span, startCol, endCol) in items) {
        var row = rowEnds.indexOfFirst { it < startCol }
        if (row == -1) {
            row = rowEnds.size
            rowEnds.add(endCol)
        } else {
            rowEnds[row] = endCol
        }
        out += AllDayRow(span, startCol, endCol, row)
    }
    return out
}

fun monthGridDays(anchor: LocalDate): List<LocalDate> {
    val first = anchor.withDayOfMonth(1)
    val gridStart = first.minusDays((first.dayOfWeek.value % 7).toLong())
    val last = first.plusMonths(1).minusDays(1)
    val gridEnd = last.plusDays((6 - last.dayOfWeek.value % 7).toLong())
    val total = ChronoUnit.DAYS.between(gridStart, gridEnd).toInt() + 1
    val target = if (total <= 35) 35 else 42
    return List(target) { gridStart.plusDays(it.toLong()) }
}
```

- [ ] **Step 5: Verify.** `./gradlew :app:assembleDebug --console=plain -q 2>&1 | grep -E "^e:|FAILED"` → expect no output.

---

### Task 3: ViewModel, Timeline shell, Day grid, nav host

**Files:** Create `timeline/TimelineViewModel.kt`, `timeline/TimelineScreen.kt`, `timeline/DayGrid.kt`, `ui/kit/CategoryIndicator.kt`. Modify `MainActivity.kt`.

**Interfaces:**
- Consumes: Task 1 `LiveHub`, `VoxSegmented`, `VoxChip`, `VoxErrorBar`, `VoxEmpty`, `Destination`; Task 2 everything.
- Produces: `TimelineViewModel`, `ViewMode`, `TimelineUi`, `TimelineScreen(token, onOpenSpan, onNewSpan)`; `CategoryIndicator(span, color)`; `DayGrid(day, spans, onSelect)`.

- [ ] **Step 1: `ui/kit/CategoryIndicator.kt`**

```kotlin
package `in`.voxagent.mobile.ui.kit

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import `in`.voxagent.mobile.spans.Span

@Composable
fun CategoryIndicator(span: Span, color: Color, modifier: Modifier = Modifier, dot: Dp = 6.dp) {
    Box(modifier.size(dot).background(color, CircleShape))
}
```

- [ ] **Step 2: `timeline/TimelineViewModel.kt`**

```kotlin
package `in`.voxagent.mobile.timeline

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import `in`.voxagent.mobile.spans.Span
import `in`.voxagent.mobile.spans.SpanCollection
import `in`.voxagent.mobile.spans.SpansApi
import `in`.voxagent.mobile.spans.dayStartMs
import `in`.voxagent.mobile.spans.monthGridDays
import `in`.voxagent.mobile.spans.weekStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate

enum class ViewMode { Day, Week, Month }

data class TimelineUi(
    val mode: ViewMode = ViewMode.Day,
    val anchor: LocalDate = LocalDate.now(),
    val selectedDay: LocalDate = LocalDate.now(),
    val spans: List<Span> = emptyList(),
    val collections: List<SpanCollection> = emptyList(),
    val collectionId: String? = null,
    val loading: Boolean = true,
    val error: String = "",
) {
    val days: List<LocalDate>
        get() = when (mode) {
            ViewMode.Day -> listOf(anchor)
            ViewMode.Week -> List(7) { anchor.plusDays(it.toLong()) }
            ViewMode.Month -> monthGridDays(anchor)
        }
    val collection: SpanCollection? get() = collections.firstOrNull { it.id == collectionId }
}

class TimelineViewModel(private val token: () -> String?) : ViewModel() {
    private val _ui = MutableStateFlow(TimelineUi())
    val ui: StateFlow<TimelineUi> = _ui.asStateFlow()
    private var loadJob: Job? = null

    init {
        loadCollections()
        reload()
    }

    fun setMode(mode: ViewMode) {
        _ui.update { s ->
            val anchor = when (mode) {
                ViewMode.Day -> s.anchor
                ViewMode.Week -> weekStart(s.anchor)
                ViewMode.Month -> s.anchor.withDayOfMonth(1)
            }
            s.copy(mode = mode, anchor = anchor, selectedDay = s.selectedDay.takeIf { mode != ViewMode.Week || it in List(7) { i -> anchor.plusDays(i.toLong()) } } ?: anchor)
        }
        reload()
    }

    fun previous() = shift(-1)

    fun next() = shift(1)

    private fun shift(direction: Long) {
        _ui.update { s ->
            val anchor = when (s.mode) {
                ViewMode.Day -> s.anchor.plusDays(direction)
                ViewMode.Week -> s.anchor.plusDays(7 * direction)
                ViewMode.Month -> s.anchor.plusMonths(direction)
            }
            s.copy(anchor = anchor, selectedDay = anchor)
        }
        reload()
    }

    fun today() {
        val today = LocalDate.now()
        _ui.update { s ->
            val anchor = when (s.mode) {
                ViewMode.Day -> today
                ViewMode.Week -> weekStart(today)
                ViewMode.Month -> today.withDayOfMonth(1)
            }
            s.copy(anchor = anchor, selectedDay = today)
        }
        reload()
    }

    fun selectDay(day: LocalDate) = _ui.update { it.copy(selectedDay = day) }

    fun openDay(day: LocalDate) {
        _ui.update { it.copy(mode = ViewMode.Day, anchor = day, selectedDay = day) }
        reload()
    }

    fun selectCollection(id: String?) {
        _ui.update { it.copy(collectionId = id) }
        reload()
    }

    fun reload() {
        val bearer = token() ?: return
        val s = _ui.value
        val days = s.days
        val from = Instant.ofEpochMilli(dayStartMs(days.first()))
        val to = Instant.ofEpochMilli(dayStartMs(days.last().plusDays(1)))
        loadJob?.cancel()
        _ui.update { it.copy(loading = true) }
        loadJob = viewModelScope.launch {
            try {
                val spans = SpansApi.getSpans(bearer, from, to, s.collectionId)
                _ui.update { it.copy(spans = spans, loading = false, error = "") }
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                _ui.update { it.copy(loading = false, error = e.message ?: "Network error") }
            }
        }
    }

    private fun loadCollections() {
        val bearer = token() ?: return
        viewModelScope.launch {
            runCatching { SpansApi.getCollections(bearer) }
                .onSuccess { list -> _ui.update { it.copy(collections = list) } }
        }
    }
}
```

- [ ] **Step 3: `timeline/DayGrid.kt`**

```kotlin
package `in`.voxagent.mobile.timeline

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.voxagent.mobile.spans.PlacedSpan
import `in`.voxagent.mobile.spans.Span
import `in`.voxagent.mobile.spans.SpanStatus
import `in`.voxagent.mobile.spans.categoryStyle
import `in`.voxagent.mobile.spans.dayStartMs
import `in`.voxagent.mobile.spans.formatAmount
import `in`.voxagent.mobile.spans.formatTime
import `in`.voxagent.mobile.spans.layoutAllDay
import `in`.voxagent.mobile.spans.layoutDay
import `in`.voxagent.mobile.ui.kit.CategoryIndicator
import `in`.voxagent.mobile.ui.theme.BorderSubtle
import `in`.voxagent.mobile.ui.theme.CoralPulse
import `in`.voxagent.mobile.ui.theme.Mist
import `in`.voxagent.mobile.ui.theme.Obsidian
import `in`.voxagent.mobile.ui.theme.SmokeDark
import kotlinx.coroutines.delay
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private val HOUR_DP = 56.dp
private const val PX_PER_MIN = 56.0 / 60.0
private const val INDENT_DP = 10
private val GUTTER = 54.dp
private val hourLabel = DateTimeFormatter.ofPattern("h a", Locale.getDefault())

@Composable
fun DayGrid(day: LocalDate, spans: List<Span>, onSelect: (Span) -> Unit, modifier: Modifier = Modifier) {
    val placed = remember(spans, day) { layoutDay(spans, day) }
    val parents = remember(placed) { placed.mapNotNull { it.span.parentId }.toSet() }
    val allDay = remember(spans, day) { layoutAllDay(spans, listOf(day)) }
    val allDayRows = (allDay.maxOfOrNull { it.row } ?: -1) + 1
    var now by remember { mutableStateOf(LocalDateTime.now()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(60_000)
            now = LocalDateTime.now()
        }
    }
    val scroll = rememberScrollState()
    val density = LocalDensity.current
    LaunchedEffect(day, spans.isEmpty()) {
        val zone = ZoneId.systemDefault()
        val earliest = spans.mapNotNull { it.startMs }
            .map { java.time.Instant.ofEpochMilli(it).atZone(zone) }
            .filter { it.toLocalDate() == day }
            .minOfOrNull { it.hour }
        val hour = earliest ?: if (day == LocalDate.now()) LocalDateTime.now().hour - 2 else 8
        scroll.scrollTo(with(density) { (maxOf(0, hour - 1) * HOUR_DP.toPx()).toInt() })
    }

    Column(modifier.fillMaxSize()) {
        if (allDayRows > 0) {
            Box(Modifier.fillMaxWidth().height((allDayRows * 24 + 6).dp)) {
                allDay.forEach { row ->
                    val style = categoryStyle(row.span.category, row.span.schemaColorToken)
                    Text(
                        row.span.title,
                        color = Mist,
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier
                            .offset(x = GUTTER + 2.dp, y = (row.row * 24 + 3).dp)
                            .padding(end = 6.dp)
                            .height(20.dp)
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(4.dp))
                            .background(lerp(Color(0xFF111214), style.dot, 0.3f))
                            .clickable { onSelect(row.span) }
                            .padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
                Text("all day", color = SmokeDark, fontSize = 9.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.width(GUTTER - 6.dp).align(Alignment.CenterStart).padding(start = 4.dp))
            }
        }
        Box(Modifier.weight(1f).fillMaxWidth().verticalScroll(scroll)) {
            Box(Modifier.fillMaxWidth().height(HOUR_DP * 24)) {
                for (h in 1..23) {
                    Text(
                        hourLabel.format(LocalDateTime.of(2000, 1, 1, h, 0)).lowercase(),
                        color = SmokeDark,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.offset(x = 4.dp, y = HOUR_DP * h - 7.dp).width(GUTTER - 10.dp),
                    )
                }
                BoxWithConstraints(
                    Modifier
                        .padding(start = GUTTER)
                        .fillMaxSize()
                        .drawBehind {
                            val step = HOUR_DP.toPx()
                            for (h in 0..23) {
                                drawLine(Color.White.copy(alpha = 0.06f), Offset(0f, h * step), Offset(size.width, h * step), 1f)
                            }
                            drawLine(BorderSubtle, Offset(0f, 0f), Offset(0f, size.height), 1f)
                        },
                ) {
                    val colWidth = maxWidth
                    placed.forEach { p ->
                        SpanBlock(p, p.span.id in parents, colWidth, onSelect)
                    }
                    if (day == now.toLocalDate()) {
                        val top = ((now.hour * 60 + now.minute) * PX_PER_MIN).dp
                        Canvas(Modifier.fillMaxWidth().height(1.dp).offset(y = top)) {
                            drawLine(CoralPulse.copy(alpha = 0.7f), Offset(0f, 0f), Offset(size.width, 0f), 2f, pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 8f)))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SpanBlock(placed: PlacedSpan, hasChildren: Boolean, colWidth: Dp, onSelect: (Span) -> Unit) {
    val span = placed.span
    val style = categoryStyle(span.category, span.schemaColorToken)
    val inset = placed.depth * INDENT_DP + 3
    val heightDp = maxOf(placed.height * PX_PER_MIN - 2, 22.0).dp
    val showTime = !placed.instant && heightDp >= 48.dp
    val amount = formatAmount(span)
    val muted = span.status == SpanStatus.Cancelled
    val border = when (span.status) {
        SpanStatus.Active -> BorderStroke(1.dp, Color.White.copy(alpha = 0.45f))
        SpanStatus.Failed -> BorderStroke(1.dp, CoralPulse)
        else -> BorderStroke(1.dp, style.border)
    }
    val bg = if (hasChildren) lerp(Color(0xFF111215), style.bg, 0.6f) else style.bg
    val shape = RoundedCornerShape(if (placed.instant) 50 else 8)
    val width = colWidth * placed.width.toFloat() - (inset + 3).dp
    val base = Modifier
        .offset(x = colWidth * placed.left.toFloat() + inset.dp, y = (placed.top * PX_PER_MIN + 2).dp)
        .alpha(if (muted) 0.4f else 1f)
        .clip(shape)
        .background(bg)
        .border(border, shape)
        .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) { onSelect(span) }
    if (placed.instant) {
        Row(
            base.height(22.dp).widthIn(max = width).padding(horizontal = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CategoryIndicator(span, style.dot)
            Text(span.title, color = Mist, fontSize = 11.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis, textDecoration = if (muted) TextDecoration.LineThrough else null)
            if (amount != null) Text(amount, color = Mist, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
        }
    } else {
        Column(
            base.width(width).height(heightDp).padding(horizontal = 8.dp, vertical = if (showTime) 8.dp else 3.dp),
            verticalArrangement = if (showTime) Arrangement.SpaceBetween else Arrangement.Center,
        ) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(span.title, color = Mist, fontSize = 11.5.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f), textDecoration = if (muted) TextDecoration.LineThrough else null)
                CategoryIndicator(span, style.dot)
            }
            if (showTime) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        formatTime(span.startMs) + (span.endMs?.let { " – ${formatTime(it)}" } ?: ""),
                        color = style.subtext,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        maxLines = 1,
                    )
                    if (amount != null) Text(amount, color = Mist, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
                }
            }
        }
    }
}
```

- [ ] **Step 4: `timeline/TimelineScreen.kt`**

```kotlin
package `in`.voxagent.mobile.timeline

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import `in`.voxagent.mobile.net.LiveHub
import `in`.voxagent.mobile.spans.Span
import `in`.voxagent.mobile.ui.VoxDarkScreen
import `in`.voxagent.mobile.ui.kit.VoxChip
import `in`.voxagent.mobile.ui.kit.VoxErrorBar
import `in`.voxagent.mobile.ui.kit.VoxSegmented
import `in`.voxagent.mobile.ui.theme.BorderSubtle
import `in`.voxagent.mobile.ui.theme.CoralPulse
import `in`.voxagent.mobile.ui.theme.GraphiteDark
import `in`.voxagent.mobile.ui.theme.Mist
import `in`.voxagent.mobile.ui.theme.Obsidian
import `in`.voxagent.mobile.ui.theme.SmokeDark
import kotlinx.coroutines.delay
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun TimelineScreen(
    token: () -> String?,
    bottomInset: androidx.compose.ui.unit.Dp,
    onOpenSpan: (Span) -> Unit,
    onNewSpan: (LocalDate) -> Unit,
    reloadSignal: Int,
) {
    val vm: TimelineViewModel = viewModel(factory = viewModelFactory { initializer { TimelineViewModel(token) } })
    val ui by vm.ui.collectAsState()

    LaunchedEffect(reloadSignal) { if (reloadSignal > 0) vm.reload() }
    LaunchedEffect(Unit) {
        val live = LiveHub.get(token)
        live.start()
        live.events.collect { event ->
            if (event.type.startsWith("span_") || event.type == "live_reconnected") vm.reload()
        }
    }
    LaunchedEffect(Unit) {
        while (true) {
            delay(15_000)
            vm.reload()
        }
    }

    VoxDarkScreen {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(bottom = bottomInset)) {
            Header(ui, vm)
            CollectionChips(ui, vm)
            if (ui.error.isNotEmpty()) VoxErrorBar(ui.error, onRetry = vm::reload)
            Box(Modifier.weight(1f).fillMaxWidth()) {
                when (ui.mode) {
                    ViewMode.Day -> DayGrid(ui.anchor, ui.spans, onOpenSpan)
                    ViewMode.Week -> Unit
                    ViewMode.Month -> Unit
                }
                Box(
                    Modifier
                        .align(Alignment.BottomEnd)
                        .padding(16.dp)
                        .size(52.dp)
                        .clip(CircleShape)
                        .background(Mist)
                        .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) { onNewSpan(ui.selectedDay) },
                    contentAlignment = Alignment.Center,
                ) { Text("+", color = Obsidian, fontSize = 26.sp, fontWeight = FontWeight.Light) }
            }
        }
    }
}

@Composable
private fun Header(ui: TimelineUi, vm: TimelineViewModel) {
    val monthFmt = remember { DateTimeFormatter.ofPattern("MMM", Locale.getDefault()) }
    val titleFmt = remember { DateTimeFormatter.ofPattern("MMMM yyyy", Locale.getDefault()) }
    val dayFmt = remember { DateTimeFormatter.ofPattern("EEEE, MMM d, yyyy", Locale.getDefault()) }
    val shortFmt = remember { DateTimeFormatter.ofPattern("MMM d", Locale.getDefault()) }
    val shortYearFmt = remember { DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.getDefault()) }
    val days = ui.days
    val range = when (ui.mode) {
        ViewMode.Day -> ui.anchor.format(dayFmt)
        else -> "${days.first().format(shortFmt)} – ${days.last().format(shortYearFmt)}"
    }
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(
                Modifier.size(42.dp).clip(RoundedCornerShape(10.dp)).background(Obsidian).border(1.dp, BorderSubtle, RoundedCornerShape(10.dp)),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(ui.anchor.format(monthFmt).uppercase(), color = CoralPulse, fontSize = 8.5.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                Text(ui.anchor.dayOfMonth.toString(), color = Mist, fontSize = 14.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
            }
            Column(Modifier.weight(1f)) {
                Text(ui.collection?.name ?: ui.anchor.format(titleFmt), color = Mist, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
                Text(range, color = SmokeDark, fontSize = 10.5.sp, fontFamily = FontFamily.Monospace, maxLines = 1)
            }
            ui.collection?.let { Text(it.kind, color = GraphiteDark, fontSize = 10.sp, fontFamily = FontFamily.Monospace) }
            Glyph(if (ui.loading) "…" else "↻") { vm.reload() }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Glyph("‹") { vm.previous() }
            Glyph("›") { vm.next() }
            Text("Today", color = Mist, fontSize = 12.sp, modifier = Modifier.clip(RoundedCornerShape(50)).clickable { vm.today() }.padding(horizontal = 10.dp, vertical = 6.dp))
            Box(Modifier.weight(1f))
            VoxSegmented(
                options = listOf(ViewMode.Day to "Day", ViewMode.Week to "Week", ViewMode.Month to "Month"),
                selected = ui.mode,
                onSelect = vm::setMode,
                modifier = Modifier.weight(2f),
            )
        }
    }
}

@Composable
private fun Glyph(text: String, onClick: () -> Unit) {
    Box(
        Modifier.size(36.dp).clip(RoundedCornerShape(10.dp)).background(Obsidian).border(1.dp, BorderSubtle, RoundedCornerShape(10.dp)).clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { Text(text, color = Mist, fontSize = 18.sp) }
}

@Composable
private fun CollectionChips(ui: TimelineUi, vm: TimelineViewModel) {
    if (ui.collections.isEmpty()) return
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        VoxChip("All", ui.collectionId == null) { vm.selectCollection(null) }
        ui.collections.forEach { c -> VoxChip(c.name, ui.collectionId == c.id) { vm.selectCollection(c.id) } }
    }
}
```
(`reloadSignal` lets the sheet in Task 5 ask the screen to reload; the `onNewSpan` day and `onOpenSpan` are handled by the host.)

- [ ] **Step 5: Host in `MainActivity.kt` `HomeScreen`.** Add near other state: `var destination by remember { mutableStateOf(Destination.Home) }`. Immediately before `VoxBottomNav(` insert:

```kotlin
      if (destination == Destination.Timeline && token != null) {
          TimelineScreen(
              token = { latestToken },
              bottomInset = 88.dp,
              onOpenSpan = {},
              onNewSpan = {},
              reloadSignal = 0,
          )
      }
```
and pass `destination = destination, onDestination = { destination = it },` into `VoxBottomNav(...)`. Add imports `in.voxagent.mobile.timeline.TimelineScreen` and `in.voxagent.mobile.ui.Destination`.

- [ ] **Step 6: Verify.** `./gradlew :app:assembleDebug --console=plain -q 2>&1 | grep -E "^e:|FAILED"` → no output. Emulator check deferred to Task 8; at this point the Day grid, header, mode switch (Week/Month empty), chips and "+" exist.

---

### Task 4: Week agenda and Month grid

**Files:** Create `timeline/WeekAgenda.kt`, `timeline/MonthGrid.kt`. Modify `timeline/TimelineScreen.kt`.

**Interfaces:** Consumes `TimelineViewModel.{selectDay,openDay,previous,next}`, `spansOnDay`, `isAllDay`. Produces `WeekAgenda(days, selected, spans, onSelectDay, onSelectSpan, onPrev, onNext)`, `MonthGrid(anchor, spans, onSelectDay)`.

- [ ] **Step 1: `timeline/WeekAgenda.kt`**

```kotlin
package `in`.voxagent.mobile.timeline

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.voxagent.mobile.spans.Span
import `in`.voxagent.mobile.spans.SpanStatus
import `in`.voxagent.mobile.spans.categoryStyle
import `in`.voxagent.mobile.spans.formatAmount
import `in`.voxagent.mobile.spans.formatTime
import `in`.voxagent.mobile.spans.isAllDay
import `in`.voxagent.mobile.spans.spansOnDay
import `in`.voxagent.mobile.ui.kit.CategoryIndicator
import `in`.voxagent.mobile.ui.kit.VoxEmpty
import `in`.voxagent.mobile.ui.theme.BorderSubtle
import `in`.voxagent.mobile.ui.theme.GraphiteDark
import `in`.voxagent.mobile.ui.theme.Mist
import `in`.voxagent.mobile.ui.theme.Obsidian
import `in`.voxagent.mobile.ui.theme.SmokeDark
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

@Composable
fun WeekAgenda(
    days: List<LocalDate>,
    selected: LocalDate,
    spans: List<Span>,
    onSelectDay: (LocalDate) -> Unit,
    onSelectSpan: (Span) -> Unit,
    onPrev: () -> Unit,
    onNext: () -> Unit,
) {
    val today = LocalDate.now()
    val daySpans = remember(spans, selected) { spansOnDay(spans, selected) }
    Column(
        Modifier.fillMaxSize().pointerInput(days) {
            var dx = 0f
            detectHorizontalDragGestures(
                onDragEnd = {
                    if (dx > 160f) onPrev() else if (dx < -160f) onNext()
                    dx = 0f
                },
                onDragCancel = { dx = 0f },
            ) { _, delta -> dx += delta }
        },
    ) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            days.forEach { day ->
                val isToday = day == today
                val isSel = day == selected
                val has = spansOnDay(spans, day).isNotEmpty()
                Column(
                    Modifier.weight(1f).clip(RoundedCornerShape(12.dp)).clickable { onSelectDay(day) }.padding(vertical = 6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(day.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.getDefault()).uppercase(), color = SmokeDark, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    Box(
                        Modifier.size(34.dp).clip(CircleShape).background(if (isSel) Mist else if (isToday) BorderSubtle else androidx.compose.ui.graphics.Color.Transparent),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(day.dayOfMonth.toString(), color = if (isSel) Obsidian else Mist, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, fontFamily = FontFamily.Monospace)
                    }
                    Box(Modifier.size(5.dp).clip(CircleShape).background(if (has) GraphiteDark else androidx.compose.ui.graphics.Color.Transparent))
                }
            }
        }
        androidx.compose.material3.HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = BorderSubtle)
        if (daySpans.isEmpty()) {
            VoxEmpty("Nothing planned")
        } else {
            LazyColumn(Modifier.fillMaxSize(), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(daySpans, key = { it.id }) { span -> AgendaRow(span, onSelectSpan) }
            }
        }
    }
}

@Composable
private fun AgendaRow(span: Span, onSelect: (Span) -> Unit) {
    val style = categoryStyle(span.category, span.schemaColorToken)
    val muted = span.status == SpanStatus.Cancelled
    val amount = formatAmount(span)
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(style.bg).border(1.dp, style.border, RoundedCornerShape(12.dp)).clickable { onSelect(span) }.padding(12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.width(74.dp)) {
            if (isAllDay(span)) {
                Text("All day", color = style.subtext, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
            } else {
                Text(formatTime(span.startMs), color = style.subtext, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                span.endMs?.let { Text(formatTime(it), color = SmokeDark, fontSize = 10.sp, fontFamily = FontFamily.Monospace) }
            }
        }
        Column(Modifier.weight(1f)) {
            Text(span.title, color = Mist, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis, textDecoration = if (muted) TextDecoration.LineThrough else null)
            if (span.status != SpanStatus.Planned) Text(span.status.label, color = GraphiteDark, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
        }
        if (amount != null) Text(amount, color = Mist, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
        CategoryIndicator(span, style.dot, dot = 8.dp)
    }
}
```

- [ ] **Step 2: `timeline/MonthGrid.kt`**

```kotlin
package `in`.voxagent.mobile.timeline

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.voxagent.mobile.spans.Span
import `in`.voxagent.mobile.spans.categoryStyle
import `in`.voxagent.mobile.spans.monthGridDays
import `in`.voxagent.mobile.spans.spansOnDay
import `in`.voxagent.mobile.ui.theme.BorderSubtle
import `in`.voxagent.mobile.ui.theme.Mist
import `in`.voxagent.mobile.ui.theme.SmokeDark
import java.time.LocalDate

private val WEEKDAYS = listOf("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

@Composable
fun MonthGrid(anchor: LocalDate, spans: List<Span>, onSelectDay: (LocalDate) -> Unit) {
    val grid = remember(anchor) { monthGridDays(anchor) }
    val today = LocalDate.now()
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
            WEEKDAYS.forEach { Text(it.uppercase(), color = SmokeDark, fontSize = 11.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.weight(1f), textAlign = androidx.compose.ui.text.style.TextAlign.Center) }
        }
        grid.chunked(7).forEach { week ->
            Row(Modifier.fillMaxWidth().weight(1f)) {
                week.forEach { day ->
                    val items = remember(spans, day) { spansOnDay(spans, day) }
                    val inMonth = day.month == anchor.month
                    Column(
                        Modifier.weight(1f).fillMaxSize().clickable { onSelectDay(day) }.alpha(if (inMonth) 1f else 0.4f).padding(vertical = 6.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Box(
                            Modifier.size(28.dp).clip(RoundedCornerShape(8.dp)).background(if (day == today) BorderSubtle else Color.Transparent),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(day.dayOfMonth.toString(), color = Mist, fontSize = 13.sp, fontWeight = if (day == today) FontWeight.Bold else FontWeight.Medium, fontFamily = FontFamily.Monospace)
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                            items.take(3).forEach { s -> Box(Modifier.size(6.dp).clip(CircleShape).background(categoryStyle(s.category, s.schemaColorToken).dot)) }
                        }
                        if (items.size > 3) Text("+${items.size - 3}", color = SmokeDark, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
                    }
                }
            }
        }
    }
}
```

- [ ] **Step 3: Wire into `TimelineScreen`.** Replace the two `-> Unit` branches:

```kotlin
                    ViewMode.Week -> WeekAgenda(ui.days, ui.selectedDay, ui.spans, vm::selectDay, onOpenSpan, vm::previous, vm::next)
                    ViewMode.Month -> MonthGrid(ui.anchor, ui.spans, vm::openDay)
```

- [ ] **Step 4: Verify.** `./gradlew :app:assembleDebug --console=plain -q 2>&1 | grep -E "^e:|FAILED"` → no output.

---

### Task 5: Span sheet (view / edit / create / delete)

**Files:** Create `timeline/SpanSheet.kt`. Modify `MainActivity.kt` (host the sheet), `timeline/TimelineScreen.kt` unchanged API.

**Interfaces:** Produces `sealed interface SheetTarget { data class Edit(val span: Span); data class New(val day: LocalDate) }`, `SpanSheet(target, collections, token, onClose, onSaved)`.

- [ ] **Step 1: `timeline/SpanSheet.kt`**

```kotlin
package `in`.voxagent.mobile.timeline

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import `in`.voxagent.mobile.spans.ExecutionType
import `in`.voxagent.mobile.spans.Span
import `in`.voxagent.mobile.spans.SpanCollection
import `in`.voxagent.mobile.spans.SpanStatus
import `in`.voxagent.mobile.spans.SpansApi
import `in`.voxagent.mobile.spans.formatAmount
import `in`.voxagent.mobile.spans.zone
import `in`.voxagent.mobile.ui.VoxPrimaryButton
import `in`.voxagent.mobile.ui.VoxTextButton
import `in`.voxagent.mobile.ui.kit.VoxChip
import `in`.voxagent.mobile.ui.theme.CoralPulse
import `in`.voxagent.mobile.ui.theme.GraphiteDark
import `in`.voxagent.mobile.ui.theme.Mist
import `in`.voxagent.mobile.ui.theme.Obsidian
import `in`.voxagent.mobile.ui.theme.SmokeDark
import `in`.voxagent.mobile.ui.voxFieldColors
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

sealed interface SheetTarget {
    data class Edit(val span: Span) : SheetTarget
    data class New(val day: LocalDate) : SheetTarget
}

private val CATEGORIES = listOf("todo", "meeting", "call", "meal", "expense", "ride", "travel", "visit", "reminder")
private val STATUSES = SpanStatus.entries

private enum class Execution(val label: String, val type: ExecutionType?) {
    LogOnly("Just log it", null),
    Autonomous("Do it for me", ExecutionType.Autonomous),
    Interactive("Do it, ask me first", ExecutionType.Interactive),
    Remind("Remind me", ExecutionType.ManualHuman),
}

private val dateTimeFormat = DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT).withZone(zone)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SpanSheet(
    target: SheetTarget,
    collections: List<SpanCollection>,
    token: () -> String?,
    onClose: () -> Unit,
    onSaved: () -> Unit,
) {
    val span = (target as? SheetTarget.Edit)?.span
    val calendarOwned = span?.source == "google_calendar"
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val draftStart = remember(target) {
        (target as? SheetTarget.New)?.let { t ->
            val now = LocalDateTime.now()
            val base = if (t.day == LocalDate.now()) now.plusHours(1).withMinute(0).withSecond(0).withNano(0) else t.day.atTime(9, 0)
            base.atZone(zone).toInstant().toEpochMilli()
        }
    }
    var title by remember { mutableStateOf(span?.title ?: "") }
    var notes by remember { mutableStateOf(span?.notes ?: "") }
    var category by remember { mutableStateOf(span?.category ?: "todo") }
    var status by remember { mutableStateOf(span?.status ?: if ((draftStart ?: Long.MAX_VALUE) < System.currentTimeMillis()) SpanStatus.Done else SpanStatus.Planned) }
    var startMs by remember { mutableStateOf(span?.startMs ?: draftStart) }
    var endMs by remember { mutableStateOf(span?.endMs ?: draftStart?.plus(3_600_000L)) }
    var execution by remember { mutableStateOf(Execution.LogOnly) }
    var amount by remember { mutableStateOf(span?.amount?.let { if (it % 1.0 == 0.0) it.toLong().toString() else it.toString() } ?: "") }
    var collectionIds by remember { mutableStateOf(span?.collectionIds ?: emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }

    fun pick(current: Long?, onPicked: (Long) -> Unit) {
        val base = (current?.let { Instant.ofEpochMilli(it).atZone(zone).toLocalDateTime() }) ?: LocalDateTime.now()
        DatePickerDialog(context, { _, y, m, d ->
            TimePickerDialog(context, { _, h, min ->
                onPicked(LocalDateTime.of(y, m + 1, d, h, min).atZone(zone).toInstant().toEpochMilli())
            }, base.hour, base.minute, false).show()
        }, base.year, base.monthValue - 1, base.dayOfMonth).show()
    }

    fun save() {
        val bearer = token() ?: return
        if (title.isBlank()) {
            error = "Give it a title"
            return
        }
        if (startMs != null && endMs != null && endMs!! < startMs!!) {
            error = "End must be after start"
            return
        }
        val parsedAmount = amount.trim().takeIf { it.isNotEmpty() }?.toDoubleOrNull()
        busy = true
        error = ""
        scope.launch {
            try {
                val startJson = startMs?.let { JsonPrimitive(Instant.ofEpochMilli(it).toString()) } ?: JsonNull
                val endJson = endMs?.let { JsonPrimitive(Instant.ofEpochMilli(it).toString()) } ?: JsonNull
                if (span != null) {
                    SpansApi.updateSpan(bearer, span.id, buildJsonObject {
                        put("notes", notes)
                        put("category", category.trim().ifEmpty { "general" })
                        if (!calendarOwned) {
                            put("title", title.trim())
                            put("status", status.wire)
                            put("start_at", startJson)
                            put("end_at", endJson)
                        }
                    })
                    val before = span.collectionIds.toSet()
                    val after = collectionIds.toSet()
                    after.filter { it !in before }.forEach { SpansApi.setSpanCollection(bearer, it, span.id, true) }
                    before.filter { it !in after }.forEach { SpansApi.setSpanCollection(bearer, it, span.id, false) }
                } else {
                    SpansApi.createSpan(bearer, buildJsonObject {
                        put("title", title.trim())
                        put("status", status.wire)
                        put("start_at", startJson)
                        put("end_at", endJson)
                        put("notes", notes)
                        put("category", category.trim().ifEmpty { "general" })
                        put("execution_type", execution.type?.wire?.let { JsonPrimitive(it) } ?: JsonNull)
                        put("data", if (parsedAmount != null) buildJsonObject { put("amount", parsedAmount); put("currency", "INR") } else JsonObject(emptyMap()))
                        put("collection_ids", buildJsonArray { collectionIds.forEach { add(JsonPrimitive(it)) } })
                    })
                }
                onSaved()
                onClose()
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                error = e.message ?: "Couldn't save"
                busy = false
            }
        }
    }

    fun remove() {
        val bearer = token() ?: return
        val id = span?.id ?: return
        busy = true
        scope.launch {
            try {
                SpansApi.deleteSpan(bearer, id)
                onSaved()
                onClose()
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                error = e.message ?: "Couldn't delete"
                busy = false
            }
        }
    }

    ModalBottomSheet(
        onDismissRequest = onClose,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = Obsidian,
        contentColor = Mist,
    ) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(if (span != null) "Edit span" else "New span", color = Mist, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                if (span != null) Text(span.source, color = SmokeDark, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                span?.let { formatAmount(it) }?.let { Text(it, color = GraphiteDark, fontSize = 11.sp, fontFamily = FontFamily.Monospace) }
            }
            if (calendarOwned) Text("Title, time and status are managed by Google Calendar. You can edit local notes and collections.", color = GraphiteDark, fontSize = 12.sp)
            OutlinedTextField(title, { title = it }, Modifier.fillMaxWidth(), label = { Text("Title") }, singleLine = true, enabled = !calendarOwned && !busy, colors = voxFieldColors())
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                TimeField("Start", startMs, !calendarOwned && !busy, Modifier.weight(1f)) { pick(startMs) { startMs = it } }
                TimeField("End", endMs, !calendarOwned && !busy, Modifier.weight(1f)) { pick(endMs ?: startMs) { endMs = it } }
            }
            if (!calendarOwned && (startMs != null || endMs != null)) {
                VoxTextButton("Clear times") { startMs = null; endMs = null }
            }
            Text("Category", color = GraphiteDark, fontSize = 12.sp)
            OutlinedTextField(category, { category = it }, Modifier.fillMaxWidth(), singleLine = true, enabled = !busy, colors = voxFieldColors())
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CATEGORIES.forEach { c -> VoxChip(c, category == c) { category = c } }
            }
            Text("Status", color = GraphiteDark, fontSize = 12.sp)
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                STATUSES.forEach { s -> VoxChip(s.label, status == s) { if (!calendarOwned && !busy) status = s } }
            }
            if (span == null) {
                Text("Vox should", color = GraphiteDark, fontSize = 12.sp)
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Execution.entries.forEach { e -> VoxChip(e.label, execution == e) { execution = e } }
                }
                OutlinedTextField(amount, { amount = it }, Modifier.fillMaxWidth(), label = { Text("Amount (₹)") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), enabled = !busy, colors = voxFieldColors())
            }
            OutlinedTextField(notes, { notes = it }, Modifier.fillMaxWidth(), label = { Text("Notes") }, minLines = 2, enabled = !busy, colors = voxFieldColors())
            if (collections.isNotEmpty()) {
                Text("Collections", color = GraphiteDark, fontSize = 12.sp)
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    collections.forEach { c ->
                        VoxChip(c.name, c.id in collectionIds) {
                            collectionIds = if (c.id in collectionIds) collectionIds - c.id else collectionIds + c.id
                        }
                    }
                }
            }
            if (error.isNotEmpty()) Text(error, color = CoralPulse, fontSize = 12.sp)
            VoxPrimaryButton(if (busy) "Saving…" else if (span != null) "Save" else "Add") { if (!busy) save() }
            if (span != null) VoxTextButton("Delete", tone = CoralPulse) { if (!busy) remove() }
        }
    }
}

@Composable
private fun TimeField(label: String, ms: Long?, enabled: Boolean, modifier: Modifier, onClick: () -> Unit) {
    OutlinedTextField(
        value = ms?.let { dateTimeFormat.format(Instant.ofEpochMilli(it)) } ?: "",
        onValueChange = {},
        modifier = modifier,
        label = { Text(label) },
        readOnly = true,
        enabled = enabled,
        colors = voxFieldColors(),
        interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }.also { source ->
            androidx.compose.runtime.LaunchedEffect(source) {
                source.interactions.collect { if (it is androidx.compose.foundation.interaction.PressInteraction.Release) onClick() }
            }
        },
    )
}
```

- [ ] **Step 2: Host the sheet in `MainActivity.kt`.** In `HomeScreen`, add `var sheet by remember { mutableStateOf<SheetTarget?>(null) }`, `var timelineReload by remember { mutableIntStateOf(0) }` (import `mutableIntStateOf`) and `var timelineCollections by remember { mutableStateOf<List<SpanCollection>>(emptyList()) }`. Change the Timeline block to:

```kotlin
      if (destination == Destination.Timeline && token != null) {
          TimelineScreen(
              token = { latestToken },
              bottomInset = 88.dp,
              onOpenSpan = { sheet = SheetTarget.Edit(it) },
              onNewSpan = { sheet = SheetTarget.New(it) },
              reloadSignal = timelineReload,
              onCollections = { timelineCollections = it },
          )
          sheet?.let { target ->
              SpanSheet(
                  target = target,
                  collections = timelineCollections,
                  token = { latestToken },
                  onClose = { sheet = null },
                  onSaved = { timelineReload += 1 },
              )
          }
      }
```
and add the parameter `onCollections: (List<SpanCollection>) -> Unit` to `TimelineScreen`, with `LaunchedEffect(ui.collections) { onCollections(ui.collections) }` inside it. Add imports for `SheetTarget`, `SpanSheet`, `SpanCollection`.

- [ ] **Step 3: Verify.** `./gradlew :app:assembleDebug --console=plain -q 2>&1 | grep -E "^e:|FAILED"` → no output.

---

### Task 6: Schema icons (24 lucide icons)

**Files:** Create `tools/gen_schema_icons.py` (repo-local script, `vox-android/tools/`), generated `ui/kit/SchemaIcons.kt`. Modify `ui/kit/CategoryIndicator.kt`.

**Interfaces:** Produces `schemaIcon(token: Int): ImageVector?` ; `CategoryIndicator` draws the icon (tinted `color`) when `span.schemaIconToken` is set, else the dot.

- [ ] **Step 1: Generator `vox-android/tools/gen_schema_icons.py`**

```python
import re, sys, urllib.request

NAMES = ["wallet","heart-pulse","utensils","car","home","briefcase","plane","dumbbell","book-open","music","film","camera","gamepad-2","shopping-bag","coffee","pill","moon","cloud-sun","phone-call","message-circle","map-pin","party-popper","users","laptop"]
URL = "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{}.svg"

def attrs(tag):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', tag))

def to_path(tag, a):
    if tag == "path":
        return a["d"]
    if tag == "circle":
        cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
        return f"M{cx - r},{cy} a{r},{r} 0 1,0 {2 * r},0 a{r},{r} 0 1,0 {-2 * r},0"
    if tag == "line":
        return f"M{a['x1']},{a['y1']} L{a['x2']},{a['y2']}"
    if tag in ("polyline", "polygon"):
        pts = a["points"].replace(",", " ").split()
        pairs = [f"{pts[i]},{pts[i + 1]}" for i in range(0, len(pts), 2)]
        return "M" + " L".join(pairs) + (" Z" if tag == "polygon" else "")
    if tag == "rect":
        x, y, w, h = float(a["x"]), float(a["y"]), float(a["width"]), float(a["height"])
        rx = float(a.get("rx", 0))
        if rx == 0:
            return f"M{x},{y} h{w} v{h} h{-w} Z"
        return (f"M{x + rx},{y} h{w - 2 * rx} a{rx},{rx} 0 0,1 {rx},{rx} v{h - 2 * rx} a{rx},{rx} 0 0,1 {-rx},{rx} "
                f"h{-(w - 2 * rx)} a{rx},{rx} 0 0,1 {-rx},{-rx} v{-(h - 2 * rx)} a{rx},{rx} 0 0,1 {rx},{-rx} Z")
    raise ValueError(tag)

out = ["package `in`.voxagent.mobile.ui.kit", "",
       "import androidx.compose.ui.graphics.Color",
       "import androidx.compose.ui.graphics.SolidColor",
       "import androidx.compose.ui.graphics.StrokeCap",
       "import androidx.compose.ui.graphics.StrokeJoin",
       "import androidx.compose.ui.graphics.vector.ImageVector",
       "import androidx.compose.ui.graphics.vector.addPathNodes",
       "import androidx.compose.ui.graphics.vector.path",
       "import androidx.compose.ui.unit.dp", "",
       "private val ICON_PATHS: List<List<String>> = listOf("]
for name in NAMES:
    svg = urllib.request.urlopen(URL.format(name)).read().decode()
    paths = []
    for tag, rest in re.findall(r"<(path|circle|line|polyline|polygon|rect)\b([^>]*?)/?>", svg):
        paths.append(to_path(tag, attrs(rest)))
    out.append("    listOf(" + ", ".join('"' + p.replace('"', '\\"') + '"' for p in paths) + "),")
out += [")", "",
        "private val cache = arrayOfNulls<ImageVector>(ICON_PATHS.size)", "",
        "fun schemaIcon(token: Int): ImageVector? {",
        "    if (token !in ICON_PATHS.indices) return null",
        "    return cache[token] ?: ImageVector.Builder(defaultWidth = 24.dp, defaultHeight = 24.dp, viewportWidth = 24f, viewportHeight = 24f).apply {",
        "        ICON_PATHS[token].forEach { d ->",
        "            addPath(addPathNodes(d), fill = null, stroke = SolidColor(Color.Black), strokeLineWidth = 2f, strokeLineCap = StrokeCap.Round, strokeLineJoin = StrokeJoin.Round)",
        "        }",
        "    }.build().also { cache[token] = it }",
        "}", ""]
open(sys.argv[1], "w").write("\n".join(out))
```

- [ ] **Step 2: Run it:** `cd vox-android && python3 tools/gen_schema_icons.py app/src/main/java/in/voxagent/mobile/ui/kit/SchemaIcons.kt` → file written, 24 icon entries (needs network). Remove the unused `path` import from the generated header if the compiler warns.

- [ ] **Step 3: Upgrade `ui/kit/CategoryIndicator.kt`**

```kotlin
package `in`.voxagent.mobile.ui.kit

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import `in`.voxagent.mobile.spans.Span

@Composable
fun CategoryIndicator(span: Span, color: Color, modifier: Modifier = Modifier, dot: Dp = 6.dp) {
    val icon = span.schemaIconToken?.let { schemaIcon(it) }
    if (icon != null) {
        Image(icon, contentDescription = null, modifier = modifier.size(dot * 2), colorFilter = ColorFilter.tint(color))
    } else {
        Box(modifier.size(dot).background(color, CircleShape))
    }
}
```

- [ ] **Step 4: Verify.** `./gradlew :app:assembleDebug --console=plain -q 2>&1 | grep -E "^e:|FAILED"` → no output.

---

### Task 7: Cleanup and wiring checks

**Files:** Modify as needed.

- [ ] **Step 1:** Remove unused imports in every file added by Tasks 1-6 (run the project's import-usage script pattern: for each `import X`, the simple name must appear elsewhere in the file, except `getValue`/`setValue`).
- [ ] **Step 2:** Confirm map scenes still work after the `SceneSource` rewrite (Task 8 step 5).
- [ ] **Step 3:** `grep -rn "darkFieldColors" app/src/main` → expect no output; `./gradlew :app:lintDebug --console=plain -q 2>&1 | grep -i unused` → no output.

---

### Task 8: Emulator verification (temporary harness, reverted afterwards)

Uses the same temporary setup as earlier sessions; every temporary edit is backed up first and restored in step 8.

- [ ] **Step 1: Back up** `vox-android/local.properties`, `app/src/main/AndroidManifest.xml`, `app/src/main/java/in/voxagent/mobile/MainActivity.kt` to the scratchpad.
- [ ] **Step 2: Temporary edits:** `VOX_API_BASE_URL=http://10.0.2.2:3011` in `local.properties`; add `android:usesCleartextTraffic="true"` to `<application`; in `MainActivity.onCreate` after `authManager = AuthManager(applicationContext)` add `intent.getStringExtra("e2e_token")?.let { SessionStore(applicationContext).save(it, java.time.Instant.now().plusSeconds(7200), "e2e@example.test", "E2E") }`.
- [ ] **Step 3: Local Core:** `docker run -d --name vox-e2e-pg -e POSTGRES_PASSWORD=e2epass -e POSTGRES_DB=vox -p 55432:5432 pgvector/pgvector:pg16`, `docker run -d --name vox-e2e-redis -p 56379:6379 redis:8-alpine`; start `vox-core/target/debug/vox-core-api` with `SUPABASE_JWT_SECRET=e2e-local-secret-not-real VOX_AUTH_TOKEN=e2e-service-token DATABASE_URL=postgres://postgres:e2epass@localhost:55432/vox REDIS_URL=redis://localhost:56379 GEMINI_API_KEY=e2e-placeholder EXA_API_KEY=e2e-placeholder PORT=3011`; wait for `/health/ready` = 200. Mint an HS256 JWT (`sub` fixed UUID, `exp` +2 h, signed with the secret), `POST /v1/me` once, insert a verified phone row into `channel_identities` for that user, then install and launch with `adb shell am start -n in.voxagent.mobile/.MainActivity --es e2e_token "$T"`; pre-grant runtime permissions with `adb shell pm grant` and tap "Allow all" if the permissions page appears.
- [ ] **Step 4: Seed spans with curl** (`POST /v1/spans`, bearer token): a 9:00-10:00 meeting, an overlapping 9:30-11:00 call, a child span with `parent_id` inside the meeting, an instant reminder at 12:00, an `expense` with `data:{"amount":450,"currency":"INR"}`, a span of exactly 24 h, a multi-day span, one with `status:"cancelled"`, one `active`, one `failed`, and a collection with two spans in it. Insert one row with `source:"google_calendar"`.
- [ ] **Step 5: Check, with a screenshot each** (`adb exec-out screencap -p`): Day grid (overlap columns, nested child, instant pill, amount chip, all-day row, now line, auto-scroll); Week strip + agenda (swipe changes week; selecting a day changes the list); Month grid (dots, today highlight, tap a day opens Day); prev/next/Today in each mode (anchor rules); collection chip filters and updates the title; "+" creates a span and it appears; tapping a span edits it; clearing times sends null (confirm via `GET`-equivalent `POST /v1/spans/list`); google_calendar span has title/time/status disabled; delete works; a span created through `curl` appears without manual refresh (live event); toggling airplane mode shows the error bar and Retry recovers; map scene push (`/v1/me/map/scene` is GET-only now; re-add the temporary POST route if needed) still renders, confirming the `SceneSource` rewrite.
- [ ] **Step 6:** `adb logcat -d | grep -E "FATAL EXCEPTION|SIGSEGV"` → expect no output.
- [ ] **Step 7: Tear down:** `pkill -f vox-core-api`, `docker rm -f vox-e2e-pg vox-e2e-redis`.
- [ ] **Step 8: Restore** the three backed-up files, rebuild with the real config, `adb install -r`, `adb shell pm clear in.voxagent.mobile`, confirm `grep -c e2e` in `MainActivity.kt` and the manifest is 0 and `local.properties` shows the production URL.

---

## Self-review

- **Spec coverage:** API parity (Task 2), live socket + polling + refresh (Tasks 1, 3), Day port incl. nesting/instants/all-day/now line/auto-scroll (Tasks 2-3), colours/status styling (Tasks 2-3), Week and Month adaptations (Task 4), sheet with calendar-owned rule, create fields, validation, collection diff, null clearing (Task 5), icons (Task 6), nav destinations/kit/viewmodel dependency (Task 1), verification (Task 8).
- **Placeholders:** none.
- **Type consistency:** `Span`/`SpanCollection`/`SpanStatus.wire`/`ExecutionType.wire`, `TimelineViewModel` methods (`setMode`, `previous`, `next`, `today`, `selectDay`, `openDay`, `selectCollection`, `reload`) match their call sites; `TimelineScreen` gains `onCollections` in Task 5 (update the Task 3 host call accordingly).
- **Known limits:** pickers use the framework date/time dialogs; header buttons use text glyphs; week uses Sunday start; `expected_version` not sent (desktop parity).
