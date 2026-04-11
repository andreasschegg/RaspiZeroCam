# tests/test_api.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("app.mediamtx.write_yaml"), \
         patch("app.mediamtx.restart_service", return_value=True):
        from app.main import app
        yield TestClient(app)


def _fake_status(**overrides):
    base = {
        "cpu_temperature": 45.0,
        "cpu_usage": 20.0,
        "memory": {"total_mb": 500, "available_mb": 300, "usage_percent": 40.0},
        "wifi": {"ssid": "Test", "signal_dbm": "65", "ip_address": "192.168.33.55"},
        "uptime_seconds": 3600,
        "camera_running": True,
        "stream_readers": 1,
    }
    base.update(overrides)
    return base


def test_get_status(client):
    with patch("app.main.get_system_status", return_value=_fake_status()):
        response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["cpu_temperature"] == 45.0
    assert data["camera_running"] is True
    assert data["stream_readers"] == 1


def test_get_config(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["resolution_width"] == 1280
    assert data["fps"] == 30
    assert data["bitrate_kbps"] == 2000


def test_put_config_triggers_mediamtx_restart(client):
    with patch("app.main.save_config"), \
         patch("app.main.mediamtx.apply_config") as mock_apply:
        response = client.put("/api/config", json={"fps": 45, "bitrate_kbps": 3000})
    assert response.status_code == 200
    data = response.json()
    assert data["fps"] == 45
    assert data["bitrate_kbps"] == 3000
    mock_apply.assert_called_once()


def test_put_config_invalid_fps_returns_422(client):
    response = client.put("/api/config", json={"fps": 120})
    assert response.status_code == 422


def test_put_config_invalid_bitrate_returns_422(client):
    response = client.put("/api/config", json={"bitrate_kbps": 10000})
    assert response.status_code == 422


def test_get_streams(client):
    with patch("app.main.get_system_status", return_value=_fake_status()):
        response = client.get("/api/streams")
    assert response.status_code == 200
    data = response.json()
    assert data["webrtc"] == "http://192.168.33.55:8889/cam/"
    assert data["rtsp"] == "rtsp://192.168.33.55:8554/cam"
    assert data["hls"].startswith("http://192.168.33.55:8888")


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
