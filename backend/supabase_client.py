"""
Supabase Client
Handles all database reads/writes.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

_supabase: Client = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key or "your-project-id" in url:
            raise RuntimeError(
                "❌ Supabase credentials missing!\n"
                "   Edit backend/.env and set SUPABASE_URL and SUPABASE_KEY"
            )

        _supabase = create_client(url, key)
        print("[Supabase] Connected")
    return _supabase


def insert_battery_reading(
    voltage: float,
    current: float,
    power: float,
    temperature: float,
    soc: float,
    soh: float = None,
    is_charging: bool = None,
    # Per-cell voltages (raw from ESP32)
    cell1: float = None,
    cell2: float = None,
    cell3: float = None,
    # Per-cell SoC predictions
    cell1_soc: float = None,
    cell2_soc: float = None,
    cell3_soc: float = None,
    min_cell_soc: float = None,   # weakest cell — used for alerts
    soc_method: str = None,
    c_rate: float = None,
) -> dict:
    """Insert a full battery reading row into Supabase."""
    client = get_supabase()

    row = {
        # Raw sensor data
        "voltage":      voltage,
        "current":      current,
        "power":        power,
        "temperature":  temperature,
        # Individual cell voltages
        "cell1_voltage": cell1,
        "cell2_voltage": cell2,
        "cell3_voltage": cell3,
        # Pack-level predictions
        "soc":          soc,
        "soh":          soh,
        "min_cell_soc": min_cell_soc,
        "is_charging":  is_charging,
        # Per-cell SoC predictions
        "cell1_soc":    cell1_soc,
        "cell2_soc":    cell2_soc,
        "cell3_soc":    cell3_soc,
        "soc_method":   soc_method,
        "c_rate":       c_rate,
        "timestamp":    datetime.utcnow().isoformat(),
    }

    result = client.table("battery_readings").insert(row).execute()
    return result.data


def get_latest_readings(limit: int = 50) -> list:
    """Fetch the most recent N readings (for the REST API endpoint)."""
    client = get_supabase()
    result = (
        client.table("battery_readings")
        .select("*")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data
