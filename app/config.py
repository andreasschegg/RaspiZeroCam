# app/config.py
import json
import os
from pydantic import BaseModel, field_validator


class AppConfig(BaseModel):
    resolution_width: int = 640
    resolution_height: int = 480
    fps: int = 15
    jpeg_quality: int = 70
    rotation: int = 0
    overlay: bool = False

    @field_validator("fps")
    @classmethod
    def validate_fps(cls, v: int) -> int:
        if not 5 <= v <= 30:
            raise ValueError(f"fps must be between 5 and 30, got {v}")
        return v

    @field_validator("jpeg_quality")
    @classmethod
    def validate_jpeg_quality(cls, v: int) -> int:
        if not 30 <= v <= 95:
            raise ValueError(f"jpeg_quality must be between 30 and 95, got {v}")
        return v

    @field_validator("rotation")
    @classmethod
    def validate_rotation(cls, v: int) -> int:
        if v not in (0, 180):
            raise ValueError(f"rotation must be 0 or 180, got {v}")
        return v

    @field_validator("resolution_width")
    @classmethod
    def validate_width(cls, v: int) -> int:
        if not 320 <= v <= 1280:
            raise ValueError(f"resolution_width must be between 320 and 1280, got {v}")
        return v

    @field_validator("resolution_height")
    @classmethod
    def validate_height(cls, v: int) -> int:
        if not 240 <= v <= 720:
            raise ValueError(f"resolution_height must be between 240 and 720, got {v}")
        return v


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
