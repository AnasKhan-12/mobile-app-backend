"""Load NASA CSVs, engineer features, and derive SoH labels."""

from __future__ import annotations

import pandas as pd

from config import (
    CHARGING_CSV,
    DISCHARGING_CSV,
    FEATURE_COLUMNS,
    NASA_CELL_CAPACITY_AH,
    SOC_TARGET,
    SOH_TARGET,
)


def _add_features(df: pd.DataFrame, phase: str) -> pd.DataFrame:
    out = df.copy()
    out["voltage"] = out["Voltage_measured"]
    out["c_rate"] = out["Current_measured"] / NASA_CELL_CAPACITY_AH
    out["soc"] = out["SoC"]
    out["phase"] = phase
    out["cycle_number"] = out["Cycle_Number"]
    out["cycle_capacity_ah"] = out["Total_charge_Ah"]
    return out


def derive_cycle_soh(discharging_df: pd.DataFrame) -> pd.Series:
    """
    SoH from discharge capacity fade relative to cycle 1 (100% at fresh cell).

    Uses each cycle's Total_charge_Ah (delivered capacity) divided by the
    first cycle's reference capacity.
    """
    cycle_capacity = discharging_df.groupby("Cycle_Number")["Total_charge_Ah"].first()
    reference_capacity = cycle_capacity.iloc[0]
    return (cycle_capacity / reference_capacity) * 100.0


def build_training_dataframe() -> pd.DataFrame:
    charging = pd.read_csv(CHARGING_CSV)
    discharging = pd.read_csv(DISCHARGING_CSV)

    cycle_soh = derive_cycle_soh(discharging)
    soh_map = cycle_soh.to_dict()

    charge = _add_features(charging, "charge")
    discharge = _add_features(discharging, "discharge")

    combined = pd.concat([charge, discharge], ignore_index=True)
    combined[SOH_TARGET] = combined["cycle_number"].map(soh_map)

    keep = FEATURE_COLUMNS + [SOC_TARGET, SOH_TARGET, "phase", "cycle_number", "cycle_capacity_ah"]
    combined = combined[keep].dropna(subset=[SOC_TARGET, SOH_TARGET])
    return combined


def split_by_cycle(
    df: pd.DataFrame, test_fraction: float, random_seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cycles = sorted(df["cycle_number"].unique())
    rng = pd.Series(cycles).sample(frac=test_fraction, random_state=random_seed)
    test_cycles = set(rng.tolist())
    test_mask = df["cycle_number"].isin(test_cycles)
    return df[~test_mask].copy(), df[test_mask].copy()
