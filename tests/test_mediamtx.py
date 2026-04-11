# tests/test_mediamtx.py
from unittest.mock import patch, MagicMock

from app import mediamtx
from app.config import AppConfig


def test_generate_yaml_contains_core_settings():
    config = AppConfig(resolution_width=1280, resolution_height=720, fps=30, bitrate_kbps=2000, rotation=0)
    yaml = mediamtx.generate_yaml(config)
    assert "rpiCameraWidth: 1280" in yaml
    assert "rpiCameraHeight: 720" in yaml
    assert "rpiCameraFPS: 30" in yaml
    assert "rpiCameraBitrate: 2000000" in yaml  # Kbps → bps
    assert "rpiCameraHFlip: false" in yaml
    assert "rpiCameraVFlip: false" in yaml
    # rpiCameraCodec is omitted — H.264 is the default on the primary stream.
    assert "rpiCameraCodec" not in yaml


def test_generate_yaml_rotation_180_sets_both_flips():
    config = AppConfig(rotation=180)
    yaml = mediamtx.generate_yaml(config)
    assert "rpiCameraHFlip: true" in yaml
    assert "rpiCameraVFlip: true" in yaml


def test_generate_yaml_bitrate_conversion():
    config = AppConfig(bitrate_kbps=3500)
    yaml = mediamtx.generate_yaml(config)
    assert "rpiCameraBitrate: 3500000" in yaml


def test_generate_yaml_has_all_protocols():
    yaml = mediamtx.generate_yaml(AppConfig())
    assert "rtspAddress: :8554" in yaml
    assert "webrtcAddress: :8889" in yaml
    assert "hlsAddress: :8888" in yaml
    assert "apiAddress: :9997" in yaml


def test_apply_config_writes_yaml_and_restarts(tmp_path):
    """apply_config should write the YAML and call systemctl restart."""
    yaml_path = tmp_path / "mediamtx.yml"
    config = AppConfig(fps=45)

    # write_yaml uses MEDIAMTX_CONFIG_PATH as a *default parameter value*, so
    # patching the module attribute isn't enough — we wrap write_yaml to inject
    # the tmp path instead.
    real_write = mediamtx.write_yaml

    def write_to_tmp(cfg, path=None):
        real_write(cfg, path=str(yaml_path))

    with patch("app.mediamtx.write_yaml", side_effect=write_to_tmp), \
         patch("app.mediamtx.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = mediamtx.apply_config(config)

    assert result is True
    assert yaml_path.exists()
    assert "rpiCameraFPS: 45" in yaml_path.read_text()
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "systemctl" in args
    assert "restart" in args
    assert "mediamtx" in args


def test_restart_service_handles_failure():
    import subprocess
    with patch("app.mediamtx.subprocess.run", side_effect=subprocess.CalledProcessError(1, "systemctl", stderr="error")):
        assert mediamtx.restart_service() is False


def test_get_stream_urls_builds_correct_scheme():
    urls = mediamtx.get_stream_urls("192.168.33.55")
    assert urls["webrtc"] == "http://192.168.33.55:8889/cam/"  # trailing slash intentional
    assert urls["rtsp"] == "rtsp://192.168.33.55:8554/cam"
    assert urls["hls"] == "http://192.168.33.55:8888/cam/index.m3u8"


def test_get_stream_state_when_mediamtx_reachable():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ready": True,
        "readers": [{"type": "webrtcSession"}, {"type": "rtspSession"}],
    }
    with patch("app.mediamtx.httpx.get", return_value=mock_response):
        state = mediamtx.get_stream_state()
    assert state["camera_running"] is True
    assert state["stream_readers"] == 2


def test_get_stream_state_when_mediamtx_unreachable():
    import httpx
    with patch("app.mediamtx.httpx.get", side_effect=httpx.ConnectError("refused")):
        state = mediamtx.get_stream_state()
    assert state["camera_running"] is False
    assert state["stream_readers"] == 0
