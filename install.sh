#!/bin/bash
# install.sh — Setup RaspiZeroCam Phase 2 on Raspberry Pi Zero 2 W
# Requires: Raspberry Pi OS Lite Bookworm 64-bit, Camera Module connected.
set -e

echo "=== RaspiZeroCam Phase 2 Installer ==="

INSTALL_DIR="/opt/raspizerocam"
MEDIAMTX_VERSION="1.9.0"
MEDIAMTX_ARCH="linux_arm64v8"

# 1. System dependencies
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip network-manager libcamera0.3

# 2. Ensure NetworkManager is managing WiFi
sudo systemctl enable NetworkManager
sudo systemctl start NetworkManager

# 3. Install mediamtx binary (arm64)
if ! command -v mediamtx >/dev/null 2>&1; then
    echo "Installing mediamtx v${MEDIAMTX_VERSION}..."
    TMP=$(mktemp -d)
    cd "${TMP}"
    wget -q "https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}/mediamtx_v${MEDIAMTX_VERSION}_${MEDIAMTX_ARCH}.tar.gz"
    tar -xzf "mediamtx_v${MEDIAMTX_VERSION}_${MEDIAMTX_ARCH}.tar.gz"
    sudo install -m 755 mediamtx /usr/local/bin/mediamtx
    cd -
    rm -rf "${TMP}"
else
    echo "mediamtx already installed: $(mediamtx --version 2>&1 | head -1)"
fi

# 4. Copy project to install dir
echo "Setting up ${INSTALL_DIR}..."
sudo mkdir -p "${INSTALL_DIR}"
sudo cp -r app "${INSTALL_DIR}/"
sudo cp requirements.txt "${INSTALL_DIR}/"

# 5. Create clean venv (no system-site-packages — we no longer need picamera2)
echo "Creating Python venv..."
sudo python3 -m venv "${INSTALL_DIR}/venv"
sudo "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
sudo "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

# 6. Write an initial mediamtx.yml (the FastAPI app will regenerate it on config changes,
#    but we need one present for mediamtx.service to start the first time).
if [ ! -f "${INSTALL_DIR}/mediamtx.yml" ]; then
    echo "Generating initial mediamtx.yml..."
    sudo "${INSTALL_DIR}/venv/bin/python" -c "
from app.config import AppConfig
from app.mediamtx import generate_yaml
with open('${INSTALL_DIR}/mediamtx.yml', 'w') as f:
    f.write(generate_yaml(AppConfig()))
" 2>/dev/null || {
        # Fallback: write a minimal default if the Python import path isn't set up yet
        sudo tee "${INSTALL_DIR}/mediamtx.yml" > /dev/null <<'EOF'
logLevel: info
api: yes
apiAddress: :9997
rtspAddress: :8554
webrtcAddress: :8889
hlsAddress: :8888
paths:
  cam:
    source: rpiCamera
    rpiCameraWidth: 1280
    rpiCameraHeight: 720
    rpiCameraFPS: 30
    rpiCameraBitrate: 2000000
    rpiCameraCodec: h264
EOF
    }
fi

# 7. Install systemd services
echo "Installing systemd services..."
sudo cp deploy/mediamtx.service /etc/systemd/system/
sudo cp deploy/raspizerocam.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mediamtx raspizerocam
sudo systemctl restart mediamtx
sudo systemctl restart raspizerocam

echo ""
echo "=== Installation complete ==="
IP=$(hostname -I | awk '{print $1}')
echo "Config portal:  http://${IP}:8080/config"
echo "WebRTC stream:  http://${IP}:8889/cam"
echo "RTSP stream:    rtsp://${IP}:8554/cam"
echo "HLS stream:     http://${IP}:8888/cam/index.m3u8"
