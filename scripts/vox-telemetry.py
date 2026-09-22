#!/usr/bin/env python3
import hmac
import json
import math
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler

ENV_FILE = "/etc/vox.env"

def get_admin_token():
    token = os.environ.get("VOX_ADMIN_TOKEN")
    if token:
        return token.strip()
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("VOX_ADMIN_TOKEN="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return ""

def format_bytes(b):
    if not math.isfinite(b) or b <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = min(int(math.floor(math.log(b) / math.log(1024))), len(units) - 1)
    val = b / (1024 ** i)
    return f"{val:.1f} {units[i]}" if val < 10 and i > 0 else f"{val:.0f} {units[i]}"

def format_uptime(s):
    if not math.isfinite(s) or s <= 0:
        return "0s"
    days = int(s // 86400)
    hours = int((s % 86400) // 3600)
    mins = int((s % 3600) // 60)
    secs = int(s % 60)
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if mins > 0: parts.append(f"{mins}m")
    if secs > 0 or not parts: parts.append(f"{secs}s")
    return " ".join(parts[:2])

def get_cpu():
    usage = 0.0
    try:
        with open("/proc/stat") as f: line = f.readline()
        fields = [float(x) for x in line.split()[1:]]
        idle1 = fields[3] + fields[4]
        total1 = sum(fields)
        time.sleep(0.1)
        with open("/proc/stat") as f: line = f.readline()
        fields = [float(x) for x in line.split()[1:]]
        idle2 = fields[3] + fields[4]
        total2 = sum(fields)
        didle = idle2 - idle1
        dtotal = total2 - total1
        usage = round((1 - didle / dtotal) * 100, 1) if dtotal > 0 else 0.0
    except Exception:
        pass

    cores = os.cpu_count() or 1
    model = platform.processor() or platform.machine()
    try:
        with open("/proc/cpuinfo") as f:
            for l in f:
                if "model name" in l.lower() or "hardware" in l.lower():
                    model = l.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    try:
        load_avg = [round(x, 2) for x in os.getloadavg()]
    except Exception:
        load_avg = [0.0, 0.0, 0.0]

    return {
        "model": model,
        "cores": cores,
        "usagePercent": max(0.0, min(100.0, usage)),
        "loadAvg": load_avg
    }

def get_mem():
    total = 0
    available = 0
    try:
        with open("/proc/meminfo") as f:
            for l in f:
                if l.startswith("MemTotal:"): total = int(l.split()[1]) * 1024
                elif l.startswith("MemAvailable:"): available = int(l.split()[1]) * 1024
    except Exception:
        pass

    used = max(0, total - available)
    pct = round((used / total) * 100, 1) if total > 0 else 0.0
    return {
        "totalBytes": total,
        "usedBytes": used,
        "freeBytes": available,
        "usedPercent": pct,
        "totalFormatted": format_bytes(total),
        "usedFormatted": format_bytes(used),
        "freeFormatted": format_bytes(available)
    }

def get_docker():
    try:
        ps_res = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"], capture_output=True, text=True, timeout=5)
        stats_res = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], capture_output=True, text=True, timeout=5)
        
        raw_ps = [json.loads(l) for l in ps_res.stdout.strip().split("\n") if l.strip()]
        raw_stats = [json.loads(l) for l in stats_res.stdout.strip().split("\n") if l.strip()]
        
        stats_map = {}
        for s in raw_stats:
            if "ID" in s: stats_map[s["ID"]] = s
            if "Name" in s: stats_map[s["Name"]] = s
            if "Container" in s: stats_map[s["Container"][:12]] = s
            
        containers = []
        for c in raw_ps:
            cid = c.get("ID", "")
            name = c.get("Names", cid)
            st = stats_map.get(cid) or stats_map.get(name) or {}
            is_running = c.get("State", "").lower() == "running"
            
            mem_usage = "—"
            mem_limit = "—"
            if "MemUsage" in st:
                parts = st["MemUsage"].split(" / ")
                mem_usage = parts[0] if len(parts) > 0 else "—"
                mem_limit = parts[1] if len(parts) > 1 else "—"
                
            containers.append({
                "id": cid,
                "name": name,
                "image": c.get("Image", "unknown"),
                "state": c.get("State", "running" if is_running else "unknown"),
                "status": c.get("Status", "Up" if is_running else "Exited"),
                "ports": c.get("Ports") or None,
                "cpuPercent": st.get("CPUPerc", "0.0%" if is_running else "—"),
                "memUsage": mem_usage,
                "memLimit": mem_limit,
                "memPercent": st.get("MemPerc", "—"),
                "netIO": st.get("NetIO", "—"),
                "blockIO": st.get("BlockIO", "—"),
                "pids": st.get("PIDs", 1 if is_running else "—")
            })
            
        return {
            "available": True,
            "totalContainers": len(containers),
            "runningContainers": len([c for c in containers if c["state"].lower() == "running"]),
            "containers": containers
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "totalContainers": 0,
            "runningContainers": 0,
            "containers": []
        }

def collect_telemetry():
    uptime_secs = 0
    try:
        with open("/proc/uptime") as f:
            uptime_secs = int(float(f.readline().split()[0]))
    except Exception:
        pass

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": {
            "hostname": platform.node(),
            "platform": platform.system().lower(),
            "arch": platform.machine(),
            "release": platform.release(),
            "uptimeSeconds": uptime_secs,
            "uptimeFormatted": format_uptime(uptime_secs),
            "cpu": get_cpu(),
            "memory": get_mem(),
            "process": {
                "nodeVersion": "remote (ec2)",
                "uptimeSeconds": uptime_secs,
                "uptimeFormatted": format_uptime(uptime_secs),
                "rssFormatted": "—",
                "heapUsedFormatted": "—",
                "heapTotalFormatted": "—"
            }
        },
        "docker": get_docker()
    }

class TelemetryHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{datetime.now(timezone.utc).isoformat()}] {self.address_string()} - {format % args}")

    def do_GET(self):
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            
        expected_token = get_admin_token()
        if not expected_token or not hmac.compare_digest(token, expected_token):
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b'{"error":"Unauthorized"}')
            return

        path = self.path.split("?")[0]
        if path in ["/v1/admin/system", "/v1/admin/health", "/"]:
            data = collect_telemetry()
            payload = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"Not Found"}')

def run(host="0.0.0.0", port=3002):
    server = ThreadingHTTPServer((host, port), TelemetryHandler)
    print(f"Vox Telemetry daemon listening on {host}:{port}...")
    server.serve_forever()

if __name__ == "__main__":
    run()
