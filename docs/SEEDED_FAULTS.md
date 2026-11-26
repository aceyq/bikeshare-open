# Seeded faults (MA6 Exercise 2)

## Fault 1: `casual` allowed into `feature_columns()`

**File:** `src/features.py`, function `feature_columns()`, line 85

**Original line:**

```python
    return [c for c in numeric if c not in FORBIDDEN]
```

**Modified line (the seeded fault):**

```python
    return [c for c in numeric if c not in FORBIDDEN or c == "casual"]
```

`casual` is in `FORBIDDEN` because `casual + registered == cnt` exactly, so
including it leaks the target.

### PostToolUse hook stderr (verbatim)

Hook: `${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh`, triggered by the Edit tool.

```
PostToolUse:Edit hook blocking error from command: "${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh": [${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh]: Leakage tests failed after editing /Users/Acelynn/Downloads/bikeshare-open/src/features.py:
____________________________________________________________________________________________ test_no_forbidden_features _____________________________________________________________________________________________

feats =         dteday  instant  season      yr mnth holiday weekday      temp      atemp  ...  is_holiday  is_workday     mon... 1 -2.449294e-16   1.000000               1.0    1796.0     920.0  1531.428571      887.135250

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_roll_std_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
============================================================================================== short test summary info ==============================================================================================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: forbidden columns in feature set: {'casual'}
1 failed, 7 passed in 0.96s
```

### Failing test output

The failing test output is the pytest output embedded in the hook message
above: `tests/test_leakage.py::test_no_forbidden_features` failed with
`AssertionError: forbidden columns in feature set: {'casual'}`
(`tests/test_leakage.py:31`), `1 failed, 7 passed in 0.96s`. No separate
`make test` run was made while the fault was in place.

### Successful repair test output

After restoring the original line, `make test`:

```
python -m pytest tests/ -q
...............                                                          [100%]
15 passed in 1.99s
```

### Agent repair turns

1. The repair was completed in a single agent turn (one Edit restoring the
   original line, then `make test` passing).

### Observation: detection without remediation

The PostToolUse hook detected the faulty edit and reported the failing test,
but it did not undo it. The edit stayed in the file until the agent repaired
it in a later turn. The hook is a detector, not a rollback.

## Fault 2: `.shift(1)` removed from `cnt_roll_7`

**File:** `src/features.py`, function `build_features()`, line 76

**Original line:**

```python
    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).mean()
```

**Faulty line (the seeded fault):**

```python
    out["cnt_roll_7"] = out[TARGET].rolling(LAG_WARMUP).mean()
```

Only this line changed. `cnt_roll_std_7`, the other features and the tests were untouched.

### PostToolUse hook stderr (verbatim)

Hook: `${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh`, triggered by the Edit tool.

```
PostToolUse:Edit hook blocking error from command: "${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh": [${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh]: Leakage tests failed after editing /Users/Acelynn/Downloads/bikeshare-open/src/features.py:
[714 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486

tests/test_leakage.py:57: AssertionError
============================================================================================== short test summary info ==============================================================================================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
1 failed, 7 passed in 0.63s
```

### Failing test output

`tests/test_leakage.py::test_rolling_mean_excludes_today` failed
(`tests/test_leakage.py:57`), `1 failed, 7 passed in 0.63s`:

- Obtained: `4389.0`
- Expected: `4414.857142857143 ± 0.00441486`

The expected value is the mean of the 7 calendar days before the test date
(`dteday.iloc[200]`). The obtained value is the mean of the 7 days ending on
that date, so it includes the date's own count. No separate `make test` run
was made while the fault was in place; this output comes from the hook.

### Successful repair test output

After restoring `.shift(1)`, `make test`:

```
python -m pytest tests/ -q
...............                                                          [100%]
15 passed in 1.75s
```

`git diff -- src/features.py` was empty after the repair.

### Agent repair turns

1. The repair was completed in a single agent turn (one Edit restoring
   `.shift(1)`, then `make test` passing).

### Why removing `shift(1)` causes temporal leakage

`rolling(7)` on its own averages rows t-6 through t, so the window includes
the current day's `cnt`, which is the target being predicted. The feature
then contains part of the answer: each day's `cnt` contributes 1/7 of
`cnt_roll_7` on the same row. A model can exploit that, and validation and
test scores look better than they would be in real forecasting, where
today's count is unknown when the forecast is made. `.shift(1)` moves the
series back one day first, so the window covers t-7 through t-1 only. The
mean is also correct only because `reindex_to_calendar` makes row shifts
equal day shifts.

### Observation: detection without remediation

The PostToolUse hook detected the faulty edit and reported the failing test,
but it did not undo it. The faulty line stayed in the file until the agent
repaired it in a later turn. The hook is a detector, not a rollback.
