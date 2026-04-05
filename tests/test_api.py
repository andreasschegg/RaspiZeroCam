# tests/test_api.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("app.main.camera") as mock_cam:
        mock_cam.is_running = True
        mock_cam.buffer = MagicMock()
        mock_cam.buffer.wait_for_frame.return_value = b"\xff\xd8fake\xff\xd9"

        from app.main import app
        yield TestClient(app)


def test_get_status(client):
    with patch("app.main.get_system_status", return_value={
        "cpu_temperature": 45.0,
        "cpu_usage": 20.0,
        "memory": {"total_mb": 500, "available_mb": 300, "usage_percent": 40.0},
        "wifi": {"ssid": "Test", "signal_dbm": "65", "ip_address": "10.0.0.1"},
        "uptime_seconds": 3600,
    }):
        response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["cpu_temperature"] == 45.0
    assert data["camera_running"] is True


def test_get_config(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["resolution_width"] == 640
    assert data["fps"] == 7


def test_put_config(client):
    with patch("app.main.save_config"):
        response = client.put("/api/config", json={"fps": 10, "overlay": True})
    assert response.status_code == 200
    data = response.json()
    assert data["fps"] == 10
    assert data["overlay"] is True


def test_put_config_invalid_value(client):
    response = client.put("/api/config", json={"fps": 0})
    assert response.status_code == 422


def test_snapshot(client):
    response = client.get("/snapshot")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_stream_returns_mjpeg_content_type(client):
    with patch("app.main.generate_mjpeg_frames", return_value=iter([b"--frame\r\ndata"])):
        response = client.get("/stream")
    assert "multipart/x-mixed-replace" in response.headers["content-type"]


def test_wifi_scan(client):
    from app.wifi import WifiNetwork
    mock_networks = [
        WifiNetwork(ssid="Net1", signal=80, encrypted=True),
        WifiNetwork(ssid="Net2", signal=45, encrypted=False),
    ]
    with patch("app.main.scan_networks", return_value=mock_networks):
        response = client.post("/config/wifi/scan")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["ssid"] == "Net1"


def test_wifi_connect_success(client):
    with patch("app.main.connect_to_network", return_value=True):
        response = client.post("/config/wifi", json={"ssid": "Test", "password": "pass"})
    assert response.status_code == 200
    assert response.json()["connected"] is True


def test_wifi_connect_failure(client):
    with patch("app.main.connect_to_network", return_value=False):
        response = client.post("/config/wifi", json={"ssid": "Bad", "password": "wrong"})
    assert response.status_code == 200
    assert response.json()["connected"] is False
