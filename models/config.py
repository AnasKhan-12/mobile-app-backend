"""Shared constants for BMS ML models (3S5P pack, NASA 1.5Ah training cells)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset"
MODELS_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = MODELS_DIR / "artifacts"

CHARGING_CSV = DATASET_DIR / "charging_100_cycles_with_soc.csv"
DISCHARGING_CSV = DATASET_DIR / "discharging_100_cycles_with_soc.csv"

# NASA single-cell rated capacity used for C-rate normalization during training.
NASA_CELL_CAPACITY_AH = 1.5

# Real 3S5P hardware: 3 Ah cells, 5 parallel branches per series stage.
HARDWARE_CELL_CAPACITY_AH = 3.0
HARDWARE_PARALLEL_COUNT = 5
HARDWARE_SERIES_COUNT = 3

# Hybrid SoC: use OCV lookup when |C-rate| is below this threshold.
# Raised from 0.05 to 0.15 because NASA discharge load data starts near 0.66C,
# leaving a gap where tree models cannot interpolate reliably.
OCV_C_RATE_THRESHOLD = 0.15

FEATURE_COLUMNS = ["voltage", "c_rate"]
SOC_TARGET = "soc"
SOH_TARGET = "soh"

SOC_MODEL_PATH = ARTIFACTS_DIR / "soc_lgbm.txt"
SOH_MODEL_PATH = ARTIFACTS_DIR / "soh_lgbm.txt"
OCV_TABLE_PATH = ARTIFACTS_DIR / "ocv_soc_lookup.csv"
TRAINING_DATA_PATH = ARTIFACTS_DIR / "engineered_training_data.csv"
METRICS_PATH = ARTIFACTS_DIR / "training_metrics.json"

RANDOM_SEED = 42
TEST_CYCLE_FRACTION = 0.2

SOC_LGBM_PARAMS = {
    "objective": "regression",
    "metric": "rmse",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
    "seed": RANDOM_SEED,
}

SOH_LGBM_PARAMS = {
    "objective": "regression",
    "metric": "rmse",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
    "seed": RANDOM_SEED,
}

NUM_BOOST_ROUNDS = 500
EARLY_STOPPING_ROUNDS = 50
