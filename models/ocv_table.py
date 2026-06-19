"""Build OCV-to-SoC lookup table from NASA rest/relaxation segments."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    CHARGING_CSV,
    DISCHARGING_CSV,
    NASA_CELL_CAPACITY_AH,
    OCV_C_RATE_THRESHOLD,
    OCV_TABLE_PATH,
)

# Fallback Li-ion OCV anchors (NASA 18650-class NCA chemistry) used when rest
# data is sparse. Documented assumption per README task brief.
STANDARD_OCV_ANCHORS = pd.DataFrame(
    {
        "voltage": [2.70, 3.00, 3.30, 3.45, 3.55, 3.62, 3.68, 3.74, 3.82, 3.92, 4.05, 4.20],
        "soc_median": [0.0, 5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
    }
)


def _rest_segments(df: pd.DataFrame) -> pd.DataFrame:
    c_rate = df["Current_measured"].abs() / NASA_CELL_CAPACITY_AH
    rest = df[c_rate < OCV_C_RATE_THRESHOLD].copy()
    rest = rest.rename(
        columns={"Voltage_measured": "voltage", "SoC": "soc"}
    )[["voltage", "soc"]]
    return rest


def build_ocv_lookup(soc_bin_size: float = 5.0) -> pd.DataFrame:
    """
    Build a monotonic OCV curve.

    NASA rest points grouped by voltage alone are biased (many near-empty segments
    at ~3.5 V). Instead, bin by known SoC during rest, take median resting voltage
    per SoC bin, then merge with standard chemistry anchors for coverage.
    """
    charging = pd.read_csv(CHARGING_CSV)
    discharging = pd.read_csv(DISCHARGING_CSV)
    rest = pd.concat(
        [_rest_segments(charging), _rest_segments(discharging)],
        ignore_index=True,
    )

    rest["soc_bin"] = (rest["soc"] / soc_bin_size).round() * soc_bin_size
    rest["soc_bin"] = rest["soc_bin"].clip(0.0, 100.0)
    nasa_curve = (
        rest.groupby("soc_bin", as_index=False)["voltage"]
        .median()
        .rename(columns={"soc_bin": "soc_median", "voltage": "voltage"})
    )

    combined = pd.concat([STANDARD_OCV_ANCHORS, nasa_curve], ignore_index=True)
    combined = combined.groupby("soc_median", as_index=False)["voltage"].median()
    combined = combined.sort_values("soc_median").reset_index(drop=True)
    combined["voltage"] = combined["voltage"].cummax()
    combined = combined.sort_values("voltage").drop_duplicates("voltage", keep="last")
    return combined.reset_index(drop=True)


def save_ocv_lookup(path=OCV_TABLE_PATH) -> pd.DataFrame:
    lookup = build_ocv_lookup()
    path.parent.mkdir(parents=True, exist_ok=True)
    lookup.to_csv(path, index=False)
    return lookup


def load_ocv_lookup(path=OCV_TABLE_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def soc_from_ocv(voltage: float, lookup: pd.DataFrame | None = None) -> float:
    """Interpolate SoC from per-cell voltage using the OCV lookup table."""
    if lookup is None:
        lookup = load_ocv_lookup()

    voltages = lookup["voltage"].to_numpy()
    socs = lookup["soc_median"].to_numpy()

    if voltage <= voltages[0]:
        return float(socs[0])
    if voltage >= voltages[-1]:
        return float(socs[-1])

    return float(np.interp(voltage, voltages, socs))
