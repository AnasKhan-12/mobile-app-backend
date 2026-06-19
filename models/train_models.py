"""Train LightGBM regressors for SoC and SoH."""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from config import (
    ARTIFACTS_DIR,
    EARLY_STOPPING_ROUNDS,
    FEATURE_COLUMNS,
    METRICS_PATH,
    NUM_BOOST_ROUNDS,
    OCV_TABLE_PATH,
    RANDOM_SEED,
    SOC_LGBM_PARAMS,
    SOC_MODEL_PATH,
    SOC_TARGET,
    SOH_LGBM_PARAMS,
    SOH_MODEL_PATH,
    SOH_TARGET,
    TEST_CYCLE_FRACTION,
    TRAINING_DATA_PATH,
)
from data_preparation import build_training_dataframe, split_by_cycle
from ocv_table import save_ocv_lookup


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    return {"rmse": rmse, "mae": mae}


def _feature_importance(model: lgb.Booster) -> dict:
    return dict(zip(FEATURE_COLUMNS, model.feature_importance(importance_type="gain").tolist()))


def train_lightgbm_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    target: str,
    params: dict,
    model_path: Path,
) -> tuple[lgb.Booster, dict]:
    x_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[target]
    x_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[target]

    train_set = lgb.Dataset(x_train, label=y_train, feature_name=FEATURE_COLUMNS)
    valid_set = lgb.Dataset(x_test, label=y_test, feature_name=FEATURE_COLUMNS, reference=train_set)

    model = lgb.train(
        params,
        train_set,
        num_boost_round=NUM_BOOST_ROUNDS,
        valid_sets=[train_set, valid_set],
        valid_names=["train", "test"],
        callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS), lgb.log_evaluation(period=0)],
    )

    train_pred = model.predict(x_train, num_iteration=model.best_iteration)
    test_pred = model.predict(x_test, num_iteration=model.best_iteration)

    metrics = {
        "target": target,
        "best_iteration": int(model.best_iteration),
        "train": _regression_metrics(y_train.to_numpy(), train_pred),
        "test": _regression_metrics(y_test.to_numpy(), test_pred),
        "feature_importance_gain": _feature_importance(model),
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))
    return model, metrics


def run_training() -> dict:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    df = build_training_dataframe()
    df.to_csv(TRAINING_DATA_PATH, index=False)

    train_df, test_df = split_by_cycle(df, TEST_CYCLE_FRACTION, RANDOM_SEED)
    ocv_lookup = save_ocv_lookup()

    _, soc_metrics = train_lightgbm_model(
        train_df, test_df, SOC_TARGET, SOC_LGBM_PARAMS, SOC_MODEL_PATH
    )
    _, soh_metrics = train_lightgbm_model(
        train_df, test_df, SOH_TARGET, SOH_LGBM_PARAMS, SOH_MODEL_PATH
    )

    summary = {
        "rows_total": len(df),
        "rows_train": len(train_df),
        "rows_test": len(test_df),
        "cycles_total": int(df["cycle_number"].nunique()),
        "ocv_lookup_points": len(ocv_lookup),
        "soc_model": soc_metrics,
        "soh_model": soh_metrics,
        "artifacts": {
            "soc_model": str(SOC_MODEL_PATH),
            "soh_model": str(SOH_MODEL_PATH),
            "ocv_table": str(OCV_TABLE_PATH),
            "training_data": str(TRAINING_DATA_PATH),
        },
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    result = run_training()
    print(json.dumps(result, indent=2))
