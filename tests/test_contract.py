"""Guard rails on the ingest contract and the trained model's behaviour."""
import pandas as pd
import pytest
from sklearn.metrics import r2_score

from src.config import ALLOWED_RAW_COLS, DATE_COL, FORBIDDEN, LAG_WARMUP, RAW, TARGET
from src.features import build_features, feature_columns, reindex_to_calendar
from src.ingest import load_raw
from src.train import MODELS, temporal_split


@pytest.fixture(scope="module")
def raw():
    return load_raw().sort_values("dteday").reset_index(drop=True)


@pytest.fixture(scope="module")
def feats(raw):
    return build_features(raw)


def test_calendar_is_complete_before_lagging(raw):
    """The reindexed frame must have no gaps, or the lags are wrong."""
    grid = reindex_to_calendar(raw)
    assert set(grid.dteday.diff().dropna().dt.days.unique()) == {1}


def test_only_expected_rows_are_dropped(raw, feats):
    """Rows may only vanish for the lag warm-up or downstream of a genuinely
    absent day -- never because an encoder produced a silent NaN.

    Accounting: the first LAG_WARMUP days have no complete history. Each
    absent calendar day m costs the LAG_WARMUP rows after it (cnt_lag_1 is
    NaN on m+1, cnt_roll_7 is NaN on m+1..m+7, cnt_lag_7 on m+7; their
    union is 7 rows). Day m itself was never in `raw`, so it is not a loss.
    The bound is exact for the current feature set; add a longer lag and
    LAG_WARMUP in src/config.py must grow with it.
    """
    full = pd.date_range(raw.dteday.min(), raw.dteday.max(), freq="D")
    missing_days = len(full) - len(raw)
    allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days
    lost = len(raw) - len(feats)
    assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"


def test_beats_the_mean_baseline(feats):
    """A model that cannot beat predicting the training mean is not a result."""
    cols = feature_columns(feats)
    train, _, test = temporal_split(feats)
    ridge = MODELS["ridge"]
    ridge.fit(train[cols], train[TARGET])
    assert r2_score(test[TARGET], ridge.predict(test[cols])) > 0.4


def test_persistence_baseline_is_reported():
    """The baseline that matters for a lag-driven model is 'yesterday again'.
    It must be in the comparison, whatever its score."""
    assert "baseline_persistence" in MODELS


def test_every_raw_column_is_explicitly_classified():
    """Each raw column must be the date, FORBIDDEN, or an ALLOWED_RAW_COLS
    entry. Classification is explicit on purpose: feature_columns() keeps any
    numeric column not in FORBIDDEN, so a new leaky column would otherwise
    become a feature without any test failing."""
    header = set(pd.read_csv(RAW, nrows=0).columns)
    unclassified = header - ALLOWED_RAW_COLS - FORBIDDEN - {DATE_COL}
    assert not unclassified, (
        f"unclassified raw columns: {sorted(unclassified)}; classify each in "
        "src/config.py as ALLOWED_RAW_COLS or FORBIDDEN"
    )


def test_raw_column_classes_are_disjoint():
    """A column in two classes (e.g. `casual` in both) defeats the check."""
    assert not (ALLOWED_RAW_COLS & FORBIDDEN)
    assert DATE_COL not in ALLOWED_RAW_COLS | FORBIDDEN
