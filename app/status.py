# app/status.py
import subprocess
import time

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
    result = subprocess.run(
        ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,IP4.ADDRESS", "device", "wifi"],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 4 and parts[0] == "yes":
            return {
                "ssid": parts[1],
                "signal_dbm": parts[2],
                "ip_address": parts[3],
            }
    return {"ssid": "", "signal_dbm": "", "ip_address": ""}


def get_uptime_seconds() -> int:
    return int(time.time() - _boot_time)


def get_system_status() -> dict:
    return {
        "cpu_temperature": get_cpu_temperature(),
        "cpu_usage": get_cpu_usage(),
        "memory": get_memory_usage(),
        "wifi": get_wifi_info(),
        "uptime_seconds": get_uptime_seconds(),
    }
