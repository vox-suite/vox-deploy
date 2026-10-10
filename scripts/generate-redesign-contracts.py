import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
source = Path(sys.argv[1])
spec = json.loads(source.read_text())
(root / "contracts/timeline-updates.openapi.json").write_text(json.dumps(spec, indent=2) + "\n")
schemas = spec["components"]["schemas"]
names = ["TimelineGroup", "TimelineEventType", "TimelineEvent", "TimelineEvidence", "TimelineEventWithEvidence", "TimelineQuery", "TimelinePage", "TimelineCountsQuery", "TimelineDayCount", "UpdateItem", "UpdatesQuery", "JobInputRequest", "JobRetryRequest", "JobActionResponse"]

def kotlin_type(s):
    if "$ref" in s:
        return s["$ref"].split("/")[-1]
    if "oneOf" in s or "anyOf" in s:
        variants = s.get("oneOf", s.get("anyOf"))
        non_null = [v for v in variants if v.get("type") != "null"]
        return kotlin_type(non_null[0]) + "?" if len(non_null) == 1 else "JsonElement"
    t = s.get("type")
    nullable = isinstance(t, list) and "null" in t
    if isinstance(t, list):
        t = next((v for v in t if v != "null"), None)
    result = {"string": "String", "boolean": "Boolean", "integer": "Long" if s.get("format") == "int64" else "Int", "number": "Double", "object": "JsonElement"}.get(t, "JsonElement")
    if t == "array":
        result = "List<" + kotlin_type(s["items"]) + ">"
    return result + ("?" if nullable else "")

lines = ["package `in`.voxagent.mobile.contracts", "", "import kotlinx.serialization.Serializable", "import kotlinx.serialization.json.JsonElement", ""]
for name in names:
    schema = schemas[name]
    required = schema.get("required", [])
    lines += ["@Serializable", "data class " + name + "("]
    for key, prop in schema["properties"].items():
        typ = kotlin_type(prop)
        optional = key not in required or typ.endswith("?")
        if optional and not typ.endswith("?"):
            typ += "?"
        lines += ["    val " + key + ": " + typ + (" = null" if optional else "") + ","]
    lines += [")", ""]
destination = root / "vox-android/app/src/main/java/in/voxagent/mobile/contracts/TimelineUpdates.kt"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text("\n".join(lines))
ts = root / "vox-desktop/src/features/api.gen.ts"
if ts.exists():
    ts.write_text(re.sub(r"/\*.*?\*/\s*", "", ts.read_text(), flags=re.S))
