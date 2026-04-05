# app/camera.py
import io
import threading
import time
import logging

logger = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import FileOutput
    HAS_PICAMERA2 = True
except ImportError:
    HAS_PICAMERA2 = False


class FrameBuffer:
    def __init__(self):
        self._frame: bytes | None = None
        self._condition = threading.Condition()

    def update(self, frame: bytes) -> None:
        with self._condition:
            self._frame = frame
            self._condition.notify_all()

    def wait_for_frame(self, timeout: float = 2.0) -> bytes | None:
        with self._condition:
            self._condition.wait(timeout=timeout)
            return self._frame


class _StreamOutput(io.BufferedIOBase):
    """Custom output that picamera2's MJPEGEncoder writes JPEG frames to."""

    def __init__(self, buffer: FrameBuffer):
        super().__init__()
        self._buffer = buffer

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:
        self._buffer.update(bytes(data))
        return len(data)

    def flush(self) -> None:
        pass


class Camera:
    def __init__(self):
        self._picam2: Picamera2 | None = None
        self._buffer = FrameBuffer()
        self._running = False

    @property
    def buffer(self) -> FrameBuffer:
        return self._buffer

    def start(self, width: int = 640, height: int = 480, fps: int = 15, rotation: int = 0, jpeg_quality: int = 70) -> None:
        if not HAS_PICAMERA2:
            logger.warning("picamera2 not available — camera disabled")
            return

        self._picam2 = Picamera2()

        from libcamera import Transform
        transform = Transform(hflip=True, vflip=True) if rotation == 180 else Transform()

        # Use picamera2's default format (XBGR8888) — what MJPEGEncoder expects natively.
        # Setting "RGB888" here causes color channel swaps because picamera2's
        # "RGB888" is actually BGR byte order (confusing naming).
        config = self._picam2.create_video_configuration(
            main={"size": (width, height)},
            transform=transform,
        )
        self._picam2.configure(config)
        self._picam2.set_controls({"FrameRate": float(fps)})

        encoder = MJPEGEncoder()
        encoder.q = jpeg_quality
        output = FileOutput(_StreamOutput(self._buffer))
        self._picam2.start_recording(encoder, output)
        self._running = True
        logger.info(f"Camera started: {width}x{height} @ {fps}fps rotation={rotation} quality={jpeg_quality}")

    def stop(self) -> None:
        if self._picam2 and self._running:
            self._picam2.stop_recording()
            self._picam2.close()
            self._running = False
            logger.info("Camera stopped")

    def restart(self, width: int, height: int, fps: int, rotation: int = 0, jpeg_quality: int = 70) -> None:
        self.stop()
        time.sleep(0.5)
        self.start(width, height, fps, rotation, jpeg_quality)

    def throttle_fps(self, new_fps: int) -> None:
        if not self._picam2 or not self._running:
            return
        self._picam2.set_controls({"FrameRate": float(new_fps)})
        logger.info(f"Throttled FPS to {new_fps}")

    @property
    def is_running(self) -> bool:
        return self._running


# Singleton instance
camera = Camera()
