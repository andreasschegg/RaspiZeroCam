import pytest
from unittest.mock import MagicMock, patch
from app.stream import generate_mjpeg_frames, render_overlay
from app.camera import FrameBuffer


def _make_fake_jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0fake_jpeg_data\xff\xd9"


def test_mjpeg_frame_format():
    buffer = FrameBuffer()

    import threading
    import time as _time

    def feed():
        _time.sleep(0.05)
        buffer.update(_make_fake_jpeg())

    threading.Thread(target=feed, daemon=True).start()

    frames = generate_mjpeg_frames(buffer, overlay=False)
    chunk = next(frames)
    assert b"--frame\r\n" in chunk
    assert b"Content-Type: image/jpeg\r\n" in chunk
    assert b"\xff\xd8" in chunk


def test_mjpeg_returns_none_on_timeout():
    buffer = FrameBuffer()
    frames = generate_mjpeg_frames(buffer, overlay=False, timeout=0.1)
    chunk = next(frames)
    assert chunk == b""


def test_overlay_renders_text_on_image():
    fake_jpeg = _make_fake_jpeg()
    status = {
        "cpu_temperature": 45.0,
        "wifi": {"ssid": "TestNet", "signal_dbm": "72", "ip_address": "10.0.0.1"},
        "uptime_seconds": 120,
    }
    config = {"resolution_width": 640, "resolution_height": 480, "fps": 15, "jpeg_quality": 70}

    with patch("app.stream.Image") as mock_image_mod:
        mock_img = MagicMock()
        mock_image_mod.open.return_value = mock_img
        mock_img.size = (640, 480)

        mock_draw_cls = MagicMock()
        with patch("app.stream.ImageDraw") as mock_draw_mod:
            mock_draw_mod.Draw.return_value = mock_draw_cls

            with patch("app.stream.BytesIO") as mock_bytes:
                mock_bytes.return_value.getvalue.return_value = b"jpeg_with_overlay"
                result = render_overlay(fake_jpeg, status, config)

    assert result == b"jpeg_with_overlay"
    mock_draw_cls.text.assert_called()


def test_generate_frames_with_overlay():
    buffer = FrameBuffer()

    import threading
    import time as _time

    def feed():
        _time.sleep(0.05)
        buffer.update(_make_fake_jpeg())

    threading.Thread(target=feed, daemon=True).start()

    with patch("app.stream.render_overlay", return_value=b"overlaid_jpeg") as mock_overlay, \
         patch("app.stream.get_system_status", return_value={}):
        frames = generate_mjpeg_frames(buffer, overlay=True)
        chunk = next(frames)
    assert b"overlaid_jpeg" in chunk
    mock_overlay.assert_called_once()
