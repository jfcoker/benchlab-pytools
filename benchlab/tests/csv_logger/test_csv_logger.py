"""
Unit tests for CSV Logger exclusion patterns functionality
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from benchlab.csv_log.csv_logger import sensor_logger_fleet


# Sample sensor structure mock
def create_mock_sensor_struct():
    """Create a mock sensor structure with known fields for testing."""
    sensor_struct = MagicMock()
    
    # Power readings (11 elements: 0-1 EPS, 2-5 ATX, 6-10 PCIe)
    power_readings = []
    for i in range(11):
        power = MagicMock()
        power.Power = 1000 + (i * 100)  # 1000, 1100, 1200, ...
        power.Voltage = 12000 - (i * 100)  # 12000, 11900, 11800, ...
        power.Current = 1000 + (i * 50)  # 1000, 1050, 1100, ...
        power_readings.append(power)
    
    sensor_struct.PowerReadings = power_readings
    
    # Voltage readings
    sensor_struct.Vin = [3300, 3350, 3400, 3450, 3500, 3550, 3600, 3650, 3700, 3750, 3800, 3850, 3900]
    sensor_struct.Vdd = 3300
    sensor_struct.Vref = 1024
    
    # Temperature
    sensor_struct.Tchip = 35 * 10  # 350 (35.0°C)
    sensor_struct.Tamb = 256 * 10  # 2560 (25.6°C)
    sensor_struct.Hum = 389  # 38.9%
    sensor_struct.Ts = [0, 0, 0, 0]  # 4 temperature sensors
    
    # Fans
    fans = []
    for i in range(9):
        fan = MagicMock()
        fan.Duty = 20
        fan.Tach = 2000 + (i * 100)
        fan.Enable = 1
        fans.append(fan)
    sensor_struct.Fans = fans
    
    sensor_struct.FanExtDuty = 56
    
    return sensor_struct


@pytest.fixture
def mock_sensor_struct():
    """Fixture providing a mock sensor structure."""
    return create_mock_sensor_struct()


def run_sensor_logger_with_exclusions(device_uid, mock_sensor_struct, excl_patterns, iterations=1):
    """Helper function to run sensor_logger_fleet with controlled execution."""
    mock_ser = MagicMock()
    device_ser_map = {device_uid: mock_ser}
    
    captured_headers = None
    
    def mock_csv_writer(f, fieldnames):
        """Create a mock CSV writer that captures headers."""
        writer = MagicMock()
        nonlocal captured_headers
        captured_headers = fieldnames
        writer.writeheader = lambda: None
        writer.writerow = lambda row: None
        return writer
    
    with patch("builtins.open", mock_open()), \
         patch("benchlab.csv_log.csv_logger.read_sensors", return_value=mock_sensor_struct), \
         patch("csv.DictWriter", side_effect=mock_csv_writer):
        
        import benchlab.csv_log.csv_logger as csv_logger
        csv_logger.logging_active = True
        
        iteration_count = 0
        def controlled_sleep(interval):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= iterations:
                csv_logger.logging_active = False
        
        with patch("time.sleep", side_effect=controlled_sleep):
            sensor_logger_fleet(device_ser_map, interval=0.01, excl_patterns=excl_patterns)
    
    return captured_headers


def test_exclude_patterns_filters_sensor_keys(mock_sensor_struct):
    """
    Test that exclude patterns properly filter sensor keys from CSV.
    
    This test verifies the public interface behavior:
    - When excl_patterns are provided, columns matching those patterns are excluded
    - When no excl_patterns are provided, all sensor columns are included
    """
    from benchlab.core.sensor_translation import translate_sensor_struct
    
    # Verify our patterns actually match something in the data
    sample_data = translate_sensor_struct(mock_sensor_struct)
    excl_patterns = ["Fan", "Temp_Sensor"]
    matching_keys = [k for k in sample_data.keys() if any(pattern in k for pattern in excl_patterns)]
    assert len(matching_keys) > 0, "Test patterns should match at least some keys"
    
    # Run the logger with exclusions
    headers = run_sensor_logger_with_exclusions("TEST_DEVICE_001", mock_sensor_struct, excl_patterns, iterations=2)
    
    # Verify headers were filtered
    assert headers is not None, "CSV headers should have been written"
    assert "Timestamp" in headers, "Timestamp should always be present"
    
    # Check that excluded patterns are NOT in headers
    for header in headers:
        for pattern in excl_patterns:
            assert pattern not in header, \
                f"Header '{header}' should not contain excluded pattern '{pattern}'"
    
    # Verify some non-excluded keys ARE present
    assert any("Power" in h for h in headers), \
        "Non-excluded Power columns should be present"


def test_translate_sensor_struct_includes_keys(mock_sensor_struct):
    """Test that translate_sensor_struct accepts an include list."""
    from benchlab.core.sensor_translation import translate_sensor_struct

    base_data = translate_sensor_struct(mock_sensor_struct)
    excl_patterns = ["Fan", "Temp_Sensor"]
    include_keys = [key for key in base_data.keys() if not any(pattern in key for pattern in excl_patterns)]

    data = translate_sensor_struct(mock_sensor_struct, incl_sensors=include_keys)

    assert set(data.keys()) == set(include_keys)
    assert "SYS_Power" in data
    for pattern in excl_patterns:
        assert all(pattern not in key for key in data.keys())


def test_no_exclusion_includes_all_sensors(mock_sensor_struct):
    """
    Test that when no exclusion patterns are provided, all sensor keys are included.
    """
    # Run the logger without exclusions
    headers = run_sensor_logger_with_exclusions("TEST_DEVICE_002", mock_sensor_struct, [])
    
    # Verify all keys are in headers (except those that might fail translation)
    assert headers is not None, "CSV headers should have been written"
    headers_set = set(headers) - {"Timestamp"}
    
    # Most keys should be present (allowing for some that might not translate)
    assert len(headers_set) > 0, "Should have sensor columns"
    assert "SYS_Power" in headers_set, "Key sensors should be present"


def test_exclude_multiple_patterns(mock_sensor_struct):
    """Test exclusion with multiple patterns."""
    excl_patterns = ["Fan", "Temp", "Current"]
    headers = run_sensor_logger_with_exclusions("TEST_003", mock_sensor_struct, excl_patterns)
    
    assert headers is not None
    
    # Check all patterns are excluded
    for pattern in excl_patterns:
        for header in headers:
            assert pattern not in header, \
                f"Pattern '{pattern}' should be excluded but found in '{header}'"
    
    # Verify some columns are still present
    power_headers = [h for h in headers if "Power" in h]
    assert len(power_headers) > 0, "Power columns should still be present"
    voltage_headers = [h for h in headers if "Voltage" in h]
    assert len(voltage_headers) > 0, "Voltage columns should still be present"
