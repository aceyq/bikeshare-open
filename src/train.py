"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import EXPERIMENTS_DIR, METRICS, PROCESSED, TARGET, TRAIN_END, VALID_END
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


class LagDifferenceRegressor(BaseEstimator, RegressorMixin):
    """Fit `estimator` on cnt - cnt_lag_1; predict by adding cnt_lag_1 back.

    The lag is read from the existing column of the same row, never
    recomputed with .diff()/.shift(): rows after the 2011-03-10 gap were
    dropped, so a row-wise difference there would span more than one day.
    A wrapped model that always predicts 0 reproduces the persistence
    baseline exactly. Predictions are on the original count scale.
    """

    def __init__(self, estimator, lag_column: str = "cnt_lag_1"):
        self.estimator = estimator
        self.lag_column = lag_column

    def fit(self, X, y):
        if self.lag_column not in X.columns:
            raise ValueError(f"difference target needs column {self.lag_column!r}")
        delta = np.asarray(y, dtype=float) - X[self.lag_column].to_numpy(dtype=float)
        self.estimator_ = clone(self.estimator).fit(X, delta)
        return self

    def predict(self, X):
        return self.estimator_.predict(X) + X[self.lag_column].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


def fit_and_score(delta_hgb: bool = False, splits: tuple = ("valid", "test")) -> dict:
    """Fit on train and score the requested splits, on the original count scale.

    With the defaults this is the standard pipeline. `delta_hgb` adds
    `hgb_delta`: the same booster (cloned from MODELS["hgb"]) fit on
    cnt - cnt_lag_1. A split not listed in `splits` is never predicted.
    """
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)
    scored = {name: part for name, part in [("valid", valid), ("test", test)] if name in splits}

    results = {
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
    }
    for split, part in scored.items():
        results[f"n_{split}"] = len(part)

    models = dict(MODELS)
    if delta_hgb:
        models["hgb_delta"] = LagDifferenceRegressor(clone(MODELS["hgb"]))
    for name, model in models.items():
        model.fit(train[cols], train[TARGET])
        results[name] = {}
        for split, part in scored.items():
            pred = model.predict(part[cols])
            results[name][split] = {
                "r2": round(float(r2_score(part[TARGET], pred)), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], pred)), 1),
            }
    return results


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Fit, score, and write metrics.")
    parser.add_argument("--delta-hgb", action="store_true",
                        help="also fit hgb on cnt - cnt_lag_1 (experiment; needs --valid-only or --final-test)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--valid-only", action="store_true",
                      help="score validation only; test rows are never predicted")
    mode.add_argument("--final-test", action="store_true",
                      help="score test once, after the decision is recorded")
    args = parser.parse_args(argv)
    if args.delta_hgb and not (args.valid_only or args.final_test):
        parser.error("--delta-hgb requires an explicit --valid-only or --final-test")
    if (args.valid_only or args.final_test) and not args.delta_hgb:
        parser.error("--valid-only/--final-test only apply together with --delta-hgb")
    return args


if __name__ == "__main__":
    args = _parse_args()
    if not args.delta_hgb:
        res = fit_and_score()
        METRICS.parent.mkdir(parents=True, exist_ok=True)
        METRICS.write_text(json.dumps(res, indent=2))
    else:
        split = "valid" if args.valid_only else "test"
        out = EXPERIMENTS_DIR / f"hgb_delta_{split}.json"
        if split == "test":
            if not (EXPERIMENTS_DIR / "hgb_delta_valid.json").exists():
                raise SystemExit("refusing --final-test: no validation run recorded yet")
            if out.exists():
                raise SystemExit(f"refusing --final-test: {out.name} exists; test is scored once")
        res = fit_and_score(delta_hgb=True, splits=(split,))
        EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
