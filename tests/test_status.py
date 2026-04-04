# tests/test_status.py
import app.status as status_module
from unittest.mock import patch, mock_open
from app.status import get_cpu_temperature, get_cpu_usage, get_memory_usage, get_wifi_info, get_system_status


def test_parse_cpu_temperature():
    with patch("builtins.open", mock_open(read_data="54321")):
        temp = get_cpu_temperature()
    assert temp == 54.3


def test_cpu_temperature_file_missing():
    with patch("builtins.open", side_effect=FileNotFoundError):
        temp = get_cpu_temperature()
    assert temp == 0.0


def test_parse_cpu_usage():
    # Reset global state so the delta is calculated from zero baseline
    status_module._prev_idle = 0
    status_module._prev_total = 0

    stat_lines = "cpu  1000 200 300 5000 100 0 50 0 0 0\n"
    # First call sets the baseline (returns 0 because d_total > 0 from 0)
    with patch("builtins.open", mock_open(read_data=stat_lines)):
        get_cpu_usage()

    # Second call with higher values shows actual usage
    stat_lines2 = "cpu  1100 200 350 5200 100 0 50 0 0 0\n"
    with patch("builtins.open", mock_open(read_data=stat_lines2)):
        usage = get_cpu_usage()

    assert isinstance(usage, float)
    assert 0.0 <= usage <= 100.0


def test_parse_memory_usage():
    meminfo = "MemTotal:      512000 kB\nMemAvailable:  256000 kB\n"
    with patch("builtins.open", mock_open(read_data=meminfo)):
        mem = get_memory_usage()
    assert mem["total_mb"] == 500.0
    assert mem["available_mb"] == 250.0
    assert mem["usage_percent"] == 50.0


def test_wifi_info_connected():
    nmcli_output = "yes:MyNetwork:72:192.168.4.100"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = nmcli_output
        mock_run.return_value.returncode = 0
        info = get_wifi_info()
    assert info["ssid"] == "MyNetwork"
    assert info["signal_dbm"] == "72"
    assert info["ip_address"] == "192.168.4.100"


def test_wifi_info_disconnected():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "no:OtherNet:30::"
        mock_run.return_value.returncode = 0
        info = get_wifi_info()
    assert info["ssid"] == ""
    assert info["ip_address"] == ""


def test_system_status_returns_all_fields():
    with patch("app.status.get_cpu_temperature", return_value=45.0), \
         patch("app.status.get_cpu_usage", return_value=23.5), \
         patch("app.status.get_memory_usage", return_value={"total_mb": 500.0, "available_mb": 300.0, "usage_percent": 40.0}), \
         patch("app.status.get_wifi_info", return_value={"ssid": "Test", "signal_dbm": "65", "ip_address": "10.0.0.1"}), \
         patch("app.status.get_uptime_seconds", return_value=3600):
        status = get_system_status()
    assert status["cpu_temperature"] == 45.0
    assert status["cpu_usage"] == 23.5
    assert status["memory"]["total_mb"] == 500.0
    assert status["wifi"]["ssid"] == "Test"
    assert status["uptime_seconds"] == 3600
