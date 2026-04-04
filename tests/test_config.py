# tests/test_config.py
import json
import os
import pytest
from app.config import AppConfig, load_config, save_config

DEFAULT_CONFIG_PATH = "test_config.json"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(DEFAULT_CONFIG_PATH):
        os.remove(DEFAULT_CONFIG_PATH)


def test_default_config_values():
    config = AppConfig()
    assert config.resolution_width == 640
    assert config.resolution_height == 480
    assert config.fps == 15
    assert config.jpeg_quality == 70
    assert config.rotation == 0
    assert config.overlay is False


def test_save_and_load_config():
    config = AppConfig(fps=10, jpeg_quality=50)
    save_config(config, DEFAULT_CONFIG_PATH)
    loaded = load_config(DEFAULT_CONFIG_PATH)
    assert loaded.fps == 10
    assert loaded.jpeg_quality == 50


def test_load_missing_file_returns_defaults():
    loaded = load_config("nonexistent.json")
    assert loaded.resolution_width == 640
    assert loaded.fps == 15


def test_partial_update():
    config = AppConfig()
    updated = config.model_copy(update={"fps": 25, "overlay": True})
    assert updated.fps == 25
    assert updated.overlay is True
    assert updated.resolution_width == 640


def test_validation_rejects_invalid_fps():
    with pytest.raises(ValueError):
        AppConfig(fps=0)


def test_validation_rejects_invalid_quality():
    with pytest.raises(ValueError):
        AppConfig(jpeg_quality=100)


def test_validation_rejects_invalid_rotation():
    with pytest.raises(ValueError):
        AppConfig(rotation=90)
