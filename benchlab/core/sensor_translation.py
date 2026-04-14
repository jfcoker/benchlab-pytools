# benchlab/core/sensor_translation.py

from .structures import SENSOR_VIN_NUM
from .utils import format_chip_temp, format_temp

def translate_sensor_struct(sensor_struct, incl_sensors=None):
    """Return a flat dict of interpreted sensor values suitable for CSV, graphs, MQTT, etc.

    incl_sensors may be provided as a list of exact sensor names to include in output dict.
    If None, all sensors are returned.
    """
    include_keys = set(incl_sensors) if incl_sensors is not None else None
    include = (lambda key: include_keys is None or key in include_keys)

    data = {}

    # Power
    power = sensor_struct.PowerReadings
    power_cpu = (power[0].Power + power[1].Power) / 1000
    power_gpu = sum([power[i].Power for i in range(6, 11)]) / 1000
    power_mb = sum([power[i].Power for i in range(2, 6)]) / 1000
    power_system = power_cpu + power_gpu + power_mb
    if include("SYS_Power"):
        data["SYS_Power"] = power_system
    if include("CPU_Power"):
        data["CPU_Power"] = power_cpu
    if include("GPU_Power"):
        data["GPU_Power"] = power_gpu
    if include("MB_Power"):
        data["MB_Power"] = power_mb

    # EPS, ATX, PCIe
    eps_labels = ["EPS1", "EPS2"]
    atx_labels = ["12V", "5V", "5VSB", "3.3V"]
    pcie_labels = ["PCIE8_1", "PCIE8_2", "PCIE8_3", "HPWR1", "HPWR2"]

    for i, label in enumerate(eps_labels):
        if include(f"{label}_Voltage"):
            data[f"{label}_Voltage"] = power[i].Voltage / 1000
        if include(f"{label}_Current"):
            data[f"{label}_Current"] = power[i].Current / 1000
        if include(f"{label}_Power"):
            data[f"{label}_Power"] = power[i].Power / 1000

    for i, label in enumerate(atx_labels):
        idx = [5, 3, 4, 2][i]
        if include(f"{label}_Voltage"):
            data[f"{label}_Voltage"] = power[idx].Voltage / 1000
        if include(f"{label}_Current"):
            data[f"{label}_Current"] = power[idx].Current / 1000
        if include(f"{label}_Power"):
            data[f"{label}_Power"] = power[idx].Power / 1000

    for i, label in enumerate(pcie_labels):
        idx = 6 + i
        if include(f"{label}_Voltage"):
            data[f"{label}_Voltage"] = power[idx].Voltage / 1000
        if include(f"{label}_Current"):
            data[f"{label}_Current"] = power[idx].Current / 1000
        if include(f"{label}_Power"):
            data[f"{label}_Power"] = power[idx].Power / 1000

    # Voltage
    vin_names = [f"VIN_{i}" for i in range(SENSOR_VIN_NUM)]
    for name, value in zip(vin_names, sensor_struct.Vin):
        if include(name):
            data[name] = value / 1000
    if include("Vdd"):
        data["Vdd"] = sensor_struct.Vdd / 1000
    if include("Vref"):
        data["Vref"] = sensor_struct.Vref / 1000

    # Temperature
    if include("Chip_Temp"):
        data["Chip_Temp"] = format_chip_temp(sensor_struct.Tchip)
    if include("Ambient_Temp"):
        data["Ambient_Temp"] = format_temp(sensor_struct.Tamb)
    if include("Humidity"):
        data["Humidity"] = sensor_struct.Hum / 10
    for i, t in enumerate(sensor_struct.Ts):
        key = f"Temp_Sensor_{i+1}"
        if include(key):
            data[key] = format_temp(t)

    # Fans
    for i, f in enumerate(sensor_struct.Fans):
        duty_key = f"Fan{i+1}_Duty"
        rpm_key = f"Fan{i+1}_RPM"
        status_key = f"Fan{i+1}_Status"
        if include(duty_key):
            data[duty_key] = f.Duty
        if include(rpm_key):
            data[rpm_key] = f.Tach
        if include(status_key):
            data[status_key] = f.Enable
    if include("FanExtDuty"):
        data["FanExtDuty"] = sensor_struct.FanExtDuty

    return data
