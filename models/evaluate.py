"""Validate inference on idle and under-load hardware scenarios."""

from __future__ import annotations

import json

from inference import BMSPredictor, HardwareTelemetry


def run_validation() -> list[dict]:
    predictor = BMSPredictor()

    scenarios = [
        {
            "name": "idle (README example)",
            "telemetry": HardwareTelemetry(pack_voltage=10.57, pack_current=0.02),
        },
        {
            "name": "discharge 2A pack",
            "telemetry": HardwareTelemetry(pack_voltage=10.2, pack_current=2.0),
        },
        {
            "name": "charge -3A pack (regenerative/charging)",
            "telemetry": HardwareTelemetry(pack_voltage=11.5, pack_current=-3.0),
        },
        {
            "name": "moderate load 5A discharge",
            "telemetry": HardwareTelemetry(pack_voltage=9.8, pack_current=5.0),
        },
    ]

    results = []
    for scenario in scenarios:
        out = predictor.predict_from_hardware(scenario["telemetry"])
        results.append(
            {
                "scenario": scenario["name"],
                "pack_voltage": scenario["telemetry"].pack_voltage,
                "pack_current": scenario["telemetry"].pack_current,
                "per_cell_voltage": round(out.per_cell_voltage, 4),
                "c_rate": round(out.c_rate, 4),
                "soc_percent": round(out.soc_percent, 2),
                "soh_percent": round(out.soh_percent, 2),
                "soc_method": out.soc_method,
            }
        )
        print(json.dumps(results[-1], indent=2))

    return results


if __name__ == "__main__":
    run_validation()
