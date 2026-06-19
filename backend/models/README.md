# backend/models/

This folder is **not** where trained models live anymore.

Trained artifacts are in the project-level `models/artifacts/` directory:

| File | Purpose |
|------|---------|
| `soc_lgbm.txt` | LightGBM SoC model (native format) |
| `soh_lgbm.txt` | LightGBM SoH model |
| `ocv_soc_lookup.csv` | OCV fallback table for idle/low C-rate |

`backend/ml_inference.py` loads them automatically via `../models/inference.py`.

## Retrain models

```powershell
cd F:\FYP-II\models
py -3 run_training.py
```

After retraining, restart the FastAPI backend so it reloads the models.
