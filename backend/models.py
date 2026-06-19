"""
Data Models (Pydantic Schemas)
==============================
Defines the shape of data flowing through the system:
  - What the MQTT messages look like (from ESP32)
  - What gets stored in Supabase
  - What the API returns to the mobile app
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── MQTT Payloads (from ESP32) ─────────────────────────────────────────────────
# Battery pack: 3S5P — 15 cells (3 series groups × 5 parallel cells each)
#   Pack voltage ≈ 12V  (unchanged from 3S1P — parallel adds capacity, not voltage)
#   Pack capacity ≈ 15Ah (5× single-cell capacity)

class PowerTempReading(BaseModel):
    """Raw payload from MQTT topic: abdul_bms/power_temp

    Example: {"voltage": 12.50, "current": 2.50, "power": 31.25, "temp": 28.40}
    All values are floats formatted to 2 decimal places.
    """
    voltage: float   # total pack voltage (~12V, sum of 3 series groups)
    current: float   # pack current (A) — higher than 3S1P due to 5P configuration
    power:   float   # total pack power (W) = voltage × current
    temp:    float   # temperature (°C)  NOTE: field name is 'temp', not 'temperature'


class CellVoltagesReading(BaseModel):
    """Raw payload from MQTT topic: abdul_bms/cell_voltages

    Example: {"cell1": 4.12, "cell2": 4.10, "cell3": 4.15}
    One reading per SERIES GROUP (not per individual cell).
    In 3S5P, each group has 5 cells in parallel — they all share the same voltage,
    so one voltage reading per group is sufficient.
    All values are floats formatted to 2 decimal places.
    """
    cell1: float   # series group 1 voltage (V)  — avg of 5 parallel cells
    cell2: float   # series group 2 voltage (V)  — avg of 5 parallel cells
    cell3: float   # series group 3 voltage (V)  — avg of 5 parallel cells


# ── Supabase Record ────────────────────────────────────────────────────────────

class BatteryRecord(BaseModel):
    """Full row written to / read from battery_readings table in Supabase."""
    id:             Optional[int]      = None

    # Raw sensor data
    voltage:        float
    current:        float
    power:          float
    temperature:    float

    # Individual cell voltages (from cell_voltages topic)
    cell1_voltage:  Optional[float]    = None
    cell2_voltage:  Optional[float]    = None
    cell3_voltage:  Optional[float]    = None

    # Pack-level ML predictions
    soc:            Optional[float]    = None   # average pack SoC (0–100 %)
    min_cell_soc:   Optional[float]    = None   # weakest cell SoC
    is_charging:    Optional[bool]     = None

    # Per-cell ML predictions
    cell1_soc:      Optional[float]    = None
    cell2_soc:      Optional[float]    = None
    cell3_soc:      Optional[float]    = None

    soh:            Optional[float]    = None   # State of Health (0–100 %)
    soc_method:     Optional[str]      = None   # ocv_lookup | lightgbm | mixed
    c_rate:         Optional[float]    = None   # per-cell C-rate used for inference

    timestamp:      Optional[datetime] = None


# ── API Response for Mobile App ────────────────────────────────────────────────

class LatestResponse(BaseModel):
    """
    Cleaned response shape returned by GET /latest.
    This is exactly what the React Native app consumes.
    """
    # Core metrics
    voltage:      float
    current:      float
    power:        float
    temperature:  float
    soc:          Optional[float]   = None   # pack SoC (%)
    soh:          Optional[float]   = None   # pack SoH (%)
    is_charging:  Optional[bool]    = None
    soc_method:   Optional[str]     = None   # ocv_lookup | lightgbm | mixed
    c_rate:       Optional[float]   = None

    # Per-cell data
    cell1_voltage: Optional[float]  = None
    cell2_voltage: Optional[float]  = None
    cell3_voltage: Optional[float]  = None
    cell1_soc:     Optional[float]  = None
    cell2_soc:     Optional[float]  = None
    cell3_soc:     Optional[float]  = None
    min_cell_soc:  Optional[float]  = None   # weakest cell — used for alerts

    timestamp:     Optional[datetime] = None
