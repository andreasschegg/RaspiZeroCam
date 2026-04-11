# app/status.py
import subprocess
import time

from app import mediamtx

_boot_time = time.time()

_prev_idle = 0
_prev_total = 0


def get_cpu_temperature() -> float:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except (FileNotFoundError, ValueError):
        return 0.0


def get_cpu_usage() -> float:
    global _prev_idle, _prev_total
    with open("/proc/stat", "r") as f:
        parts = f.readline().split()
    idle = int(parts[4])
    total = sum(int(p) for p in parts[1:])
    d_idle = idle - _prev_idle
    d_total = total - _prev_total
    _prev_idle = idle
    _prev_total = total
    if d_total == 0:
        return 0.0
    return round((1 - d_idle / d_total) * 100, 1)


def get_memory_usage() -> dict:
    mem = {}
    with open("/proc/meminfo", "r") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                mem["total_mb"] = round(int(line.split()[1]) / 1024, 1)
            elif line.startswith("MemAvailable:"):
                mem["available_mb"] = round(int(line.split()[1]) / 1024, 1)
    mem["usage_percent"] = round((1 - mem["available_mb"] / mem["total_mb"]) * 100, 1)
    return mem


def get_wifi_info() -> dict:
    # Get SSID + signal from active WiFi connection (IN-USE is marked with "*")
    result = subprocess.run(
        ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL", "device", "wifi", "list"],
        capture_output=True, text=True
    )
    ssid = ""
    signal = ""
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 3 and parts[0] == "*":
            ssid = parts[1]
            signal = parts[2]
            break

    # Get IP address separately from the wlan0 device
    ip_result = subprocess.run(
        ["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", "wlan0"],
        capture_output=True, text=True
    )
    ip_address = ""
    for line in ip_result.stdout.strip().split("\n"):
        if line.startswith("IP4.ADDRESS"):
            # Format: IP4.ADDRESS[1]:192.168.33.168/24
            value = line.split(":", 1)[1] if ":" in line else ""
            ip_address = value.split("/")[0] if "/" in value else value
            break

    return {"ssid": ssid, "signal_dbm": signal, "ip_address": ip_address}


def get_uptime_seconds() -> int:
    return int(time.time() - _boot_time)


# Cache for get_system_status — nmcli is fast enough on Pi Zero 2 W to use
# a short 3-second TTL, which keeps the UI feeling live without hammering nmcli.
_status_cache: dict | None = None
_status_cache_time: float = 0.0
_STATUS_CACHE_TTL = 3.0  # seconds


def get_system_status() -> dict:
    global _status_cache, _status_cache_time
    now = time.time()
    if _status_cache is not None and (now - _status_cache_time) < _STATUS_CACHE_TTL:
        # Return cached data with fresh uptime + mediamtx stream state.
        cached = dict(_status_cache)
        cached["uptime_seconds"] = get_uptime_seconds()
        cached.update(mediamtx.get_stream_state())
        return cached

    _status_cache = {
        "cpu_temperature": get_cpu_temperature(),
        "cpu_usage": get_cpu_usage(),
        "memory": get_memory_usage(),
        "wifi": get_wifi_info(),
        "uptime_seconds": get_uptime_seconds(),
    }
    _status_cache_time = now
    result = dict(_status_cache)
    result.update(mediamtx.get_stream_state())
    return result
