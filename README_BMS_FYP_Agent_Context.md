# BMS ML Project — Agent Context & Task Brief

## Project Summary
Final Year Project: ML-based Battery Management System (BMS) for a **3S5P Li-ion battery pack**
(3 cells in series, 5 cells in parallel per series stage). Goal: predict **State of Charge (SoC)**
and **State of Health (SoH)** from live hardware telemetry.

Training data source: **NASA Battery Dataset** — single-cell data, cell rating **1.5Ah**, same
chemistry as the real hardware's cells.

Real hardware's actual cells: **3Ah**, same chemistry as NASA cells, arranged as 3S5P (3 series
groups, 5 parallel cells per group).

---

## Hardware Telemetry (MQTT payload format)

**Topic: `abdul_bms/power_temp`**
```json
{
  "voltage": 10.57,
  "current": 0.02,
  "power": 0.27,
  "temp": 30.22
}
```
- `voltage`: pack voltage (sum of 3 series stages)
- `current`: pack-level current (sum across the 5 parallel branches)
- `power`: pack power
- `temp`: ambient/pack temperature in °C — **NOT to be used as a model feature** (see below)

**Topic: `abdul_bms/cell_voltages`**
```json
{
  "cell1": 3.5,
  "cell2": 3.57,
  "cell3": 3.54
}
```
- These are the 3 series-stage voltages (each represents a group of 5 parallel cells, which sit
  at the same voltage by definition since they're in parallel).
- Sanity check: sum of cell1+cell2+cell3 should ≈ pack voltage (small gap expected due to wiring/
  lead resistance — currently observed: 10.61V summed vs 10.57V reported, ~0.04V drop, considered
  acceptable).

---

## Key Problems Already Diagnosed (do not re-derive — these are settled conclusions)

### 1. Current scaling for 5P
Hardware reports **pack current**. To get per-cell current, divide by number of parallel
branches (5):
```
per_cell_current = pack_current / 5
```

### 2. Capacity mismatch (1.5Ah training cells vs 3Ah real cells)
Raw amps don't transfer between cells of different capacity — same current = different stress
(C-rate) on different-sized cells. Fix: **normalize current to C-rate**, not raw amps, for both
the NASA training data and the live hardware data, so they're on the same relative scale.
```
C_rate = per_cell_current / cell_capacity_Ah
```
- For NASA training data: `C_rate = nasa_current / 1.5`
- For real hardware data: `C_rate = (pack_current / 5) / 3.0`

This C-rate feature should **replace raw current** as the model's current-related input.

### 3. Temperature — EXCLUDED as a feature
NASA dataset was collected in a narrow lab temp range (~3.6–16.7°C). Real hardware operates at
~30°C ambient — completely outside that range. Tree-based models (LightGBM) cannot extrapolate
past their training split boundaries; they plateau/flatline at the edge value for any input
beyond the max seen in training. This caused the model to flatline to SoC = 0% regardless of
current, since temperature dominated the prediction once pinned at its OOD leaf.

**Decision: drop temperature entirely from the feature set.** Documented as a known limitation
for the FYP report (future work: retrain with pack-level data across a wider thermal range).

### 4. Voltage feature
Per-cell voltages were considered but **descoped** to keep the feature set simple and structurally
identical to NASA's single-cell-voltage format. Use:
```
voltage_feature = pack_voltage / 3
```
as an approximation of per-cell voltage (acceptable for a healthy, reasonably balanced pack).
Per-cell voltage imbalance tracking (`max(cell1,cell2,cell3) - min(...)`) is a documented
"future work" item for SoH/cell-balancing detection, not required for this iteration's SoC model.

### 5. Idle / near-zero current problem
At idle (e.g., observed 0.02A pack current → ~0.0013C per cell), current is far below anything
in NASA's training distribution, even at their "rest" points. At near-zero current, terminal
voltage ≈ open-circuit voltage (OCV), and OCV maps directly to SoC for Li-ion cells.

**Required solution: hybrid model, not pure ML.**
- If `C_rate < threshold` (suggested threshold: 0.05C) → estimate SoC via an **OCV-to-SoC lookup
  table** (extract from NASA's rest/relaxation periods in the dataset, or use a standard Li-ion
  OCV-SoC curve for the matching chemistry).
- Else → use the trained **LightGBM model** for SoC prediction.

---

## Final Feature Set for Model Training

| Feature | Source / Formula |
|---|---|
| `voltage` | `pack_voltage / 3` |
| `c_rate` | `(pack_current / 5) / 3.0` (real hardware) or `current / 1.5` (NASA training data) |
| ~~`temperature`~~ | **excluded** |

Target variables: **SoC** (primary) and **SoH** (secondary — derive from capacity fade /
internal resistance trends in NASA dataset if available; document method used).

Model: **LightGBM** (regressor) — confirmed choice, no need to evaluate alternatives unless
accuracy is unacceptably poor after retraining.

---

## Tasks for the Agent

1. **Load and inspect the NASA battery dataset.** Identify available columns (voltage, current,
   temperature, capacity, cycle data, SoC/SoH labels or derivable proxies).

2. **Feature engineering on NASA data:**
   - Compute `c_rate = current / 1.5`
   - Use existing single-cell voltage as `voltage` (no rescaling needed on NASA's side)
   - Drop temperature column
   - Confirm/derive SoC labels (and SoH labels if present, e.g. from capacity fade across cycles)

3. **Extract or build an OCV-SoC lookup table** from NASA's rest/relaxation segments (low/zero
   current periods), to be used for the idle-mode fallback. If rest periods are insufficient,
   use a standard published OCV-SoC curve for the matching Li-ion chemistry and note this as an
   assumption in documentation.

4. **Train a LightGBM regression model** for SoC using `[voltage, c_rate]` as features. Do a
   proper train/test split, report RMSE/MAE, and output `feature_importances_`.

5. **Train/derive a SoH estimation approach** — propose a reasonable method given NASA dataset
   structure (e.g., capacity fade ratio per cycle, or a second LightGBM model if suitable labels
   exist) and document the reasoning, since this hasn't been fully scoped yet.

6. **Build inference logic / switching function** that:
   - Accepts the real hardware payload format (`power_temp` + `cell_voltages` topics)
   - Computes `voltage = pack_voltage / 3` and `c_rate = (pack_current/5) / 3.0`
   - If `c_rate < 0.05` → return OCV-lookup-based SoC
   - Else → return LightGBM-predicted SoC
   - Also returns SoH prediction

7. **Validate** against the example payloads provided above (idle case: voltage=10.57,
   current=0.02, and at least one synthetic "under load" case, e.g. current=2A and current=-3A
   pack-level) and confirm outputs are non-zero and sensible (not flatlined).

8. **Output deliverables:**
   - Cleaned/engineered training dataset (or script to produce it)
   - Trained LightGBM model file (e.g. `.txt` or `.pkl`)
   - OCV-SoC lookup table (CSV or dict in code)
   - Inference script/function with the switching logic above
   - Brief metrics summary (RMSE/MAE, feature importances)

---

## Constraints / Things NOT to change
- Do not reintroduce temperature as a model feature.
- Do not add per-cell (cell1/cell2/cell3) voltages as separate model features — use
  `pack_voltage / 3` only, per the descoped decision above.
- Keep LightGBM as the model type; don't switch algorithms without strong justification.
- Preserve the hybrid OCV (idle) + LightGBM (active load) architecture — do not replace with a
  single end-to-end model, as this is a deliberate design decision for the FYP.
