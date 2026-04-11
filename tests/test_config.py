# tests/test_config.py
import os
import pytest
from pydantic import ValidationError
from app.config import AppConfig, load_config, save_config

DEFAULT_CONFIG_PATH = "test_config.json"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(DEFAULT_CONFIG_PATH):
        os.remove(DEFAULT_CONFIG_PATH)


def test_default_config_values():
    config = AppConfig()
    assert config.resolution_width == 1280
    assert config.resolution_height == 720
    assert config.fps == 30
    assert config.bitrate_kbps == 2000
    assert config.rotation == 0


def test_save_and_load_config():
    config = AppConfig(fps=60, bitrate_kbps=3500)
    save_config(config, DEFAULT_CONFIG_PATH)
    loaded = load_config(DEFAULT_CONFIG_PATH)
    assert loaded.fps == 60
    assert loaded.bitrate_kbps == 3500


def test_load_missing_file_returns_defaults():
    loaded = load_config("nonexistent.json")
    assert loaded.resolution_width == 1280
    assert loaded.fps == 30


def test_partial_update():
    config = AppConfig()
    updated = config.model_copy(update={"fps": 45, "bitrate_kbps": 4000})
    assert updated.fps == 45
    assert updated.bitrate_kbps == 4000
    assert updated.resolution_width == 1280


def test_validation_rejects_fps_below_min():
    with pytest.raises(ValidationError):
        AppConfig(fps=10)


def test_validation_rejects_fps_above_max():
    with pytest.raises(ValidationError):
        AppConfig(fps=120)


def test_validation_rejects_bitrate_below_min():
    with pytest.raises(ValidationError):
        AppConfig(bitrate_kbps=100)


def test_validation_rejects_bitrate_above_max():
    with pytest.raises(ValidationError):
        AppConfig(bitrate_kbps=10000)


def test_validation_rejects_invalid_rotation():
    with pytest.raises(ValidationError):
        AppConfig(rotation=90)


def test_validation_rejects_resolution_too_small():
    with pytest.raises(ValidationError):
        AppConfig(resolution_width=320, resolution_height=240)
