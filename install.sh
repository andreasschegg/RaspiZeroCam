#!/bin/bash
# install.sh — Setup RaspiZeroCam on Raspberry Pi Zero
set -e

echo "=== RaspiZeroCam Installer ==="

# Install system dependencies
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libcamera-apps python3-picamera2 network-manager

# Ensure NetworkManager manages wlan0
echo "Configuring NetworkManager..."
sudo systemctl enable NetworkManager
sudo systemctl start NetworkManager

# Create install directory
INSTALL_DIR="/opt/raspizerocam"
echo "Setting up ${INSTALL_DIR}..."
sudo mkdir -p ${INSTALL_DIR}
sudo cp -r . ${INSTALL_DIR}/

# Create virtual environment
echo "Creating Python venv..."
cd ${INSTALL_DIR}
python3 -m venv venv --system-site-packages
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Install systemd service
echo "Installing systemd service..."
sudo cp raspizerocam.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable raspizerocam
sudo systemctl start raspizerocam

echo "=== Installation complete ==="
echo "Stream available at http://$(hostname -I | awk '{print $1}'):8080/stream"
echo "Config portal at http://$(hostname -I | awk '{print $1}'):8080/config"
