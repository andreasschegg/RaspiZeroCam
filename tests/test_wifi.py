from unittest.mock import patch, MagicMock
from app.wifi import scan_networks, connect_to_network, get_saved_networks, delete_network, WifiNetwork, start_ap, stop_ap, get_mac_suffix


def test_parse_scan_results():
    nmcli_output = (
        "MyNetwork:80:WPA2\n"
        "OpenNet:45:\n"
        "StrongNet:92:WPA2\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = nmcli_output
        mock_run.return_value.returncode = 0
        networks = scan_networks()
    assert len(networks) == 3
    assert networks[0].ssid == "MyNetwork"
    assert networks[0].signal == 80
    assert networks[0].encrypted is True
    assert networks[1].ssid == "OpenNet"
    assert networks[1].encrypted is False


def test_connect_to_network_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        result = connect_to_network("TestSSID", "password123")
    assert result is True
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "TestSSID" in cmd
    assert "password123" in cmd


def test_connect_to_network_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error"
        result = connect_to_network("BadSSID", "wrong")
    assert result is False


def test_get_saved_networks():
    nmcli_output = "Home-WiFi:802-11-wireless\nPixel-Hotspot:802-11-wireless\nEthernet:802-3-ethernet\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = nmcli_output
        mock_run.return_value.returncode = 0
        saved = get_saved_networks()
    assert saved == ["Home-WiFi", "Pixel-Hotspot"]


def test_delete_network():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = delete_network("OldNetwork")
    assert result is True
    cmd = mock_run.call_args[0][0]
    assert "delete" in cmd
    assert "OldNetwork" in cmd


def test_get_mac_suffix():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "AA:BB:CC:DD:EE:FF\n"
        mock_run.return_value.returncode = 0
        suffix = get_mac_suffix()
    assert suffix == "EEFF"


def test_start_ap_uses_mac_suffix():
    with patch("app.wifi.get_mac_suffix", return_value="A3F2"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        start_ap()
    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)
    assert "RaspiZeroCam-A3F2" in cmd_str
