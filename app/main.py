# app/main.py
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from app import mediamtx
from app.config import AppConfig, load_config, save_config
from app.status import get_system_status
from app.wifi import (
    connect_to_network,
    delete_network,
    ensure_connected,
    get_saved_networks,
    scan_networks,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_config: AppConfig = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config
    _config = load_config()

    # WiFi boot sequence (non-blocking — config portal must remain reachable in AP mode)
    def wifi_boot():
        while not ensure_connected():
            time.sleep(5)
    threading.Thread(target=wifi_boot, daemon=True).start()

    # Write mediamtx.yml from current config. The mediamtx.service is managed
    # by systemd and runs independently; we just make sure its config file
    # reflects the latest AppConfig at boot.
    try:
        mediamtx.write_yaml(_config)
        mediamtx.restart_service()
    except Exception as exc:
        logger.error(f"Failed to apply mediamtx config at startup: {exc}")

    logger.info("RaspiZeroCam started")
    yield
    logger.info("RaspiZeroCam stopped")


app = FastAPI(title="RaspiZeroCam", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# --- Status & Config ---

@app.get("/api/status")
def api_status():
    return get_system_status()


@app.get("/api/config")
def api_get_config():
    return _config.model_dump()


@app.put("/api/config")
def api_put_config(updates: dict):
    global _config
    merged = _config.model_dump()
    merged.update(updates)
    try:
        new_config = AppConfig(**merged)
    except ValidationError as exc:
        errors = [
            {"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=errors)

    camera_changed = (
        new_config.resolution_width != _config.resolution_width
        or new_config.resolution_height != _config.resolution_height
        or new_config.fps != _config.fps
        or new_config.bitrate_kbps != _config.bitrate_kbps
        or new_config.rotation != _config.rotation
    )

    _config = new_config
    save_config(_config)

    if camera_changed:
        mediamtx.apply_config(_config)

    return _config.model_dump()


@app.get("/api/streams")
def api_streams():
    """Return the stream URLs using the host the client connected through."""
    from fastapi import Request  # noqa: F401 — used via dependency injection
    # We need the request's host header to build URLs, so use a dependency.
    # For simplicity here, use wlan0 IP from status if available.
    status = get_system_status()
    ip = status.get("wifi", {}).get("ip_address") or "localhost"
    return mediamtx.get_stream_urls(ip)


# --- WiFi Config ---

class WifiCredentials(BaseModel):
    ssid: str
    password: str


@app.post("/config/wifi/scan")
def wifi_scan():
    networks = scan_networks()
    return [{"ssid": n.ssid, "signal": n.signal, "encrypted": n.encrypted} for n in networks]


@app.post("/config/wifi")
def wifi_connect(creds: WifiCredentials):
    success = connect_to_network(creds.ssid, creds.password)
    return {"connected": success, "ssid": creds.ssid}


@app.get("/config/wifi/saved")
def wifi_saved():
    return get_saved_networks()


@app.delete("/config/wifi/{name}")
def wifi_delete(name: str):
    success = delete_network(name)
    return {"deleted": success, "name": name}


# --- Config Portal ---

@app.get("/config")
def config_portal():
    return FileResponse("app/static/index.html")
