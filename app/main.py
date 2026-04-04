# app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from app.camera import camera
from app.config import AppConfig, load_config, save_config
from app.status import get_system_status
from app.stream import generate_mjpeg_frames, render_overlay
import threading

from app.wifi import scan_networks, connect_to_network, get_saved_networks, delete_network, ensure_connected

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_config: AppConfig = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config
    _config = load_config()

    # WiFi boot sequence (non-blocking for AP mode — portal still needs to serve)
    def wifi_boot():
        while not ensure_connected():
            pass  # Retry until connected
    wifi_thread = threading.Thread(target=wifi_boot, daemon=True)
    wifi_thread.start()

    camera.start(
        width=_config.resolution_width,
        height=_config.resolution_height,
        fps=_config.fps,
    )
    logger.info("RaspiZeroCam started")
    yield
    camera.stop()
    logger.info("RaspiZeroCam stopped")


app = FastAPI(title="RaspiZeroCam", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# --- Stream Endpoints ---

@app.get("/stream")
def stream(overlay: bool = Query(False)):
    use_overlay = overlay or _config.overlay
    return StreamingResponse(
        generate_mjpeg_frames(
            camera.buffer,
            overlay=use_overlay,
            config=_config.model_dump() if use_overlay else None,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/snapshot")
def snapshot():
    frame = camera.buffer.wait_for_frame(timeout=2.0)
    if frame is None:
        return Response(status_code=503, content="No frame available")
    return Response(content=frame, media_type="image/jpeg")


@app.get("/snapshot/info")
def snapshot_info():
    frame = camera.buffer.wait_for_frame(timeout=2.0)
    if frame is None:
        return Response(status_code=503, content="No frame available")
    status = get_system_status()
    result = render_overlay(frame, status, _config.model_dump())
    return Response(content=result, media_type="image/jpeg")


# --- REST API ---

@app.get("/api/status")
def api_status():
    status = get_system_status()
    status["camera_running"] = camera.is_running
    return status


@app.get("/api/config")
def api_get_config():
    return _config.model_dump()


@app.put("/api/config")
def api_put_config(updates: dict):
    global _config
    new_config = _config.model_copy(update=updates)
    # Re-validate through Pydantic — raise 422 on invalid values
    try:
        new_config = AppConfig(**new_config.model_dump())
    except ValidationError as exc:
        from fastapi import HTTPException
        # Serialize errors to plain dicts (ctx may contain non-serializable exceptions)
        errors = [
            {
                "loc": e.get("loc"),
                "msg": e.get("msg"),
                "type": e.get("type"),
            }
            for e in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=errors)

    resolution_changed = (
        new_config.resolution_width != _config.resolution_width
        or new_config.resolution_height != _config.resolution_height
        or new_config.fps != _config.fps
    )

    _config = new_config
    save_config(_config)

    if resolution_changed:
        camera.restart(
            width=_config.resolution_width,
            height=_config.resolution_height,
            fps=_config.fps,
        )

    return _config.model_dump()


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
    from fastapi.responses import FileResponse
    return FileResponse("app/static/index.html")
