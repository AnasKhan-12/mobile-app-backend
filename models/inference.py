"""Hybrid SoC (OCV + LightGBM) and LightGBM SoH inference for live hardware."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np

from config import (
    FEATURE_COLUMNS,
    HARDWARE_CELL_CAPACITY_AH,
    HARDWARE_PARALLEL_COUNT,
    HARDWARE_SERIES_COUNT,
    OCV_C_RATE_THRESHOLD,
    SOC_MODEL_PATH,
    SOH_MODEL_PATH,
)
from ocv_table import load_ocv_lookup, soc_from_ocv


@dataclass
class HardwareTelemetry:
    pack_voltage: float
    pack_current: float
    power: float | None = None
    temp: float | None = None  # recorded but not used as a model feature


@dataclass
class PredictionResult:
    soc_percent: float
    soh_percent: float
    soc_method: str
    per_cell_voltage: float
    c_rate: float


class BMSPredictor:
    def __init__(
        self,
        soc_model_path: Path = SOC_MODEL_PATH,
        soh_model_path: Path = SOH_MODEL_PATH,
        ocv_threshold: float = OCV_C_RATE_THRESHOLD,
    ):
        self.soc_model = lgb.Booster(model_file=str(soc_model_path))
        self.soh_model = lgb.Booster(model_file=str(soh_model_path))
        self.ocv_lookup = load_ocv_lookup()
        self.ocv_threshold = ocv_threshold

    @staticmethod
    def hardware_features(pack_voltage: float, pack_current: float) -> tuple[float, float]:
        per_cell_voltage = pack_voltage / HARDWARE_SERIES_COUNT
        per_cell_current = pack_current / HARDWARE_PARALLEL_COUNT
        c_rate = per_cell_current / HARDWARE_CELL_CAPACITY_AH
        return per_cell_voltage, c_rate

    def predict_soc(self, voltage: float, c_rate: float) -> tuple[float, str]:
        if abs(c_rate) < self.ocv_threshold:
            soc = soc_from_ocv(voltage, self.ocv_lookup)
            return float(np.clip(soc, 0.0, 100.0)), "ocv_lookup"

        features = np.array([[voltage, c_rate]], dtype=np.float64)
        soc = float(self.soc_model.predict(features)[0])
        return float(np.clip(soc, 0.0, 100.0)), "lightgbm"

    def predict_soh(self, voltage: float, c_rate: float) -> float:
        features = np.array([[voltage, c_rate]], dtype=np.float64)
        soh = float(self.soh_model.predict(features)[0])
        return float(np.clip(soh, 0.0, 100.0))

    def predict_from_hardware(self, telemetry: HardwareTelemetry) -> PredictionResult:
        voltage, c_rate = self.hardware_features(telemetry.pack_voltage, telemetry.pack_current)
        soc, method = self.predict_soc(voltage, c_rate)
        soh = self.predict_soh(voltage, c_rate)
        return PredictionResult(
            soc_percent=soc,
            soh_percent=soh,
            soc_method=method,
            per_cell_voltage=voltage,
            c_rate=c_rate,
        )

    def predict_from_mqtt(
        self,
        power_temp: dict,
        cell_voltages: dict | None = None,
    ) -> PredictionResult:
        """
        Accept payloads from abdul_bms/power_temp (+ optional cell_voltages).

        Pack voltage from power_temp is used; cell voltages are sanity-checked only.
        """
        pack_voltage = float(power_temp["voltage"])
        pack_current = float(power_temp["current"])

        if cell_voltages is not None:
            summed = sum(float(cell_voltages[k]) for k in ("cell1", "cell2", "cell3"))
            gap = abs(summed - pack_voltage)
            if gap > 0.15:
                pass  # optional: log wiring/lead drop warning

        return self.predict_from_hardware(
            HardwareTelemetry(
                pack_voltage=pack_voltage,
                pack_current=pack_current,
                power=power_temp.get("power"),
                temp=power_temp.get("temp"),
            )
        )


def predict(
    pack_voltage: float,
    pack_current: float,
    predictor: BMSPredictor | None = None,
) -> PredictionResult:
    if predictor is None:
        predictor = BMSPredictor()
    return predictor.predict_from_hardware(
        HardwareTelemetry(pack_voltage=pack_voltage, pack_current=pack_current)
    )
