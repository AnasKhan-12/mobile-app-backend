"""
ML Inference — hybrid OCV + LightGBM SoC/SoH
==============================================
Wraps the trained models in ../models/ (LightGBM .txt + OCV CSV).

Features: voltage (per series group), c_rate — temperature excluded.
SoC: OCV lookup when |c_rate| < 0.15, else LightGBM.
SoH: LightGBM on every reading (no rolling buffer).
"""

from __future__ import annotations

import sys
from pathlib import Path

MODELS_PKG = Path(__file__).resolve().parent.parent / "models"
if str(MODELS_PKG) not in sys.path:
    sys.path.insert(0, str(MODELS_PKG))

from inference import BMSPredictor  # noqa: E402

_predictor: BMSPredictor | None = None


def _get_predictor() -> BMSPredictor:
    global _predictor
    if _predictor is None:
        print(f"[ML] Loading models from: {MODELS_PKG / 'artifacts'}")
        _predictor = BMSPredictor()
        print("[ML] SoC + SoH models loaded (hybrid OCV + LightGBM)")
    return _predictor


def _format_soc_method(method: str) -> str:
    if method == "ocv_lookup":
        return "ocv_lookup"
    if method == "lightgbm":
        return "lightgbm"
    return "mixed"


def predict_soc(
    voltage: float,
    current: float,
    temperature: float,
    power: float,
    cell1: float | None = None,
    cell2: float | None = None,
    cell3: float | None = None,
) -> dict:
    """
    Predict SoC and SoH for the 3S5P battery pack.

    temperature and power are stored in the DB but not passed to the ML models.
    """
    del temperature, power  # kept for API compatibility with mqtt_client

    predictor = _get_predictor()
    _, c_rate = predictor.hardware_features(voltage, current)
    # Sensor polarity: negative current = charging, positive = discharging
    is_charging = bool(current < 0)

    if all(v is not None for v in (cell1, cell2, cell3)):
        soc1, method1 = predictor.predict_soc(cell1, c_rate)
        soc2, method2 = predictor.predict_soc(cell2, c_rate)
        soc3, method3 = predictor.predict_soc(cell3, c_rate)
        methods = {method1, method2, method3}
        soc_method = method1 if len(methods) == 1 else "mixed"
        pack_soc = round((soc1 + soc2 + soc3) / 3, 2)
        min_cell_soc = round(min(soc1, soc2, soc3), 2)
        print(
            f"[ML] Group SoCs -> G1={soc1:.1f}% G2={soc2:.1f}% G3={soc3:.1f}% "
            f"({soc_method})"
        )
    else:
        per_cell_voltage, _ = predictor.hardware_features(voltage, current)
        pack_soc, soc_method = predictor.predict_soc(per_cell_voltage, c_rate)
        pack_soc = round(pack_soc, 2)
        min_cell_soc = pack_soc
        soc1 = soc2 = soc3 = pack_soc
        print(f"[ML] Pack SoC -> {pack_soc:.1f}% ({soc_method})")

    per_cell_voltage, _ = predictor.hardware_features(voltage, current)
    soh = round(predictor.predict_soh(per_cell_voltage, c_rate), 2)
    print(f"[ML] SoH -> {soh:.1f}%  c_rate={c_rate:.4f}")

    return {
        "soc": pack_soc,
        "soh": soh,
        "min_cell_soc": min_cell_soc,
        "cell1_soc": round(soc1, 2),
        "cell2_soc": round(soc2, 2),
        "cell3_soc": round(soc3, 2),
        "is_charging": is_charging,
        "soc_method": _format_soc_method(soc_method),
        "c_rate": round(c_rate, 4),
    }
