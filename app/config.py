# app/config.py
import json
import os
from typing import Literal

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Camera + stream configuration for Phase 2 (mediamtx + H.264)."""

    resolution_width: int = Field(default=1280, ge=640, le=1920)
    resolution_height: int = Field(default=720, ge=480, le=1080)
    fps: int = Field(default=30, ge=15, le=60)
    bitrate_kbps: int = Field(default=2000, ge=500, le=5000)
    rotation: Literal[0, 180] = 0


CONFIG_PATH = "/opt/raspizerocam/config.json"


def load_config(path: str = CONFIG_PATH) -> AppConfig:
    if not os.path.exists(path):
        return AppConfig()
    with open(path, "r") as f:
        data = json.load(f)
    return AppConfig(**data)


def save_config(config: AppConfig, path: str = CONFIG_PATH) -> None:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(config.model_dump(), f, indent=2)
