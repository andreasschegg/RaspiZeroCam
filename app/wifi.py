import subprocess
import time
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WifiNetwork:
    ssid: str
    signal: int
    encrypted: bool


def scan_networks() -> list[WifiNetwork]:
    subprocess.run(["nmcli", "device", "wifi", "rescan"], capture_output=True)
    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
        capture_output=True, text=True
    )
    networks = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 3:
            networks.append(WifiNetwork(
                ssid=parts[0],
                signal=int(parts[1]) if parts[1] else 0,
                encrypted=bool(parts[2].strip()),
            ))
    return networks


def connect_to_network(ssid: str, password: str) -> bool:
    result = subprocess.run(
        ["nmcli", "device", "wifi", "connect", ssid, "password", password],
        capture_output=True, text=True
    )
    return result.returncode == 0


def get_saved_networks() -> list[str]:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
        capture_output=True, text=True
    )
    networks = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "802-11-wireless":
            networks.append(parts[0])
    return networks


def delete_network(name: str) -> bool:
    result = subprocess.run(
        ["nmcli", "connection", "delete", name],
        capture_output=True, text=True
    )
    return result.returncode == 0


def get_mac_suffix() -> str:
    result = subprocess.run(
        ["cat", "/sys/class/net/wlan0/address"],
        capture_output=True, text=True
    )
    mac = result.stdout.strip().upper()
    return mac.replace(":", "")[-4:]


def start_ap() -> None:
    suffix = get_mac_suffix()
    ssid = f"RaspiZeroCam-{suffix}"
    subprocess.run([
        "nmcli", "device", "wifi", "hotspot",
        "ifname", "wlan0",
        "ssid", ssid,
        "band", "bg",
        "channel", "6",
    ], capture_output=True, text=True)


def stop_ap() -> None:
    subprocess.run(
        ["nmcli", "connection", "down", "Hotspot"],
        capture_output=True, text=True
    )


AP_TIMEOUT_SECONDS = 300  # 5 minutes


def ensure_connected() -> bool:
    """Try saved networks first. If none connect, start AP and wait for config."""
    saved = get_saved_networks()
    if saved:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("yes:"):
                logger.info(f"Already connected to {line.split(':')[1]}")
                return True

        for network in saved:
            logger.info(f"Trying saved network: {network}")
            res = subprocess.run(
                ["nmcli", "connection", "up", network],
                capture_output=True, text=True
            )
            if res.returncode == 0:
                logger.info(f"Connected to {network}")
                return True

    logger.info("No known network found — starting AP fallback")
    start_ap()

    start_time = time.time()
    while time.time() - start_time < AP_TIMEOUT_SECONDS:
        time.sleep(10)
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("yes:") and "RaspiZeroCam" not in line:
                logger.info("Connected via config portal")
                stop_ap()
                return True

    logger.info("AP timeout — retrying network scan")
    stop_ap()
    return False
