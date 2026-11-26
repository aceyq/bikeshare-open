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

## Fault 3: weather label validation removed from `encode_weather()`

Unlike Faults 1 and 2, the existing verification suite did not detect this
fault. It was found, a test was written to close the gap, and the fault was
then seeded a second time to confirm the strengthened suite catches it.

**File:** `src/features.py`, function `encode_weather()`

**Original code:**

```python
    known = series.dropna()
    unknown = set(known.unique()) - set(WEATHER_ORDER)
    if unknown:
        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
    return series.map(WEATHER_ORDER).astype(float)
```

**Faulty code (the seeded fault):** only the conditional raise was removed.
The `known` and `unknown` assignments were left in place, now unused.

```python
    known = series.dropna()
    unknown = set(known.unique()) - set(WEATHER_ORDER)
    return series.map(WEATHER_ORDER).astype(float)
```

Without the raise, an unseen weather label maps silently to NaN through
`.map()`, and the later `dropna()` in `build_features` deletes those rows
with no error or warning. The `encode_weather` docstring describes this
failure mode.

### Chronology

#### Attempt 1: fault seeded, no detection

1. The `if unknown: raise ValueError(...)` block was removed.
2. **The PostToolUse hook produced no error.** The edit was accepted silently.
3. The leakage suite was run explicitly, with the fault in place:

   ```
   $ python -m pytest tests/test_leakage.py -q
   ........                                                                 [100%]
   8 passed in 0.47s
   ```

   **Original leakage suite: 8 passed in 0.47s despite the fault.**

#### The verification gap

None of the 8 original tests calls `encode_weather()` with an unknown label.
`build_features` only ever sees the three known labels (`GOOD`, `MISTY`,
`BAD`) in the real data, so the validation branch was never exercised. The
suite checked leakage properties, not the encoder's failure behaviour. A
removed guard that only matters for unexpected input is invisible to tests
that use only expected input.

#### Gap closed: new synthetic test

`test_encode_weather_rejects_unknown_label` was added to
`tests/test_leakage.py`, with `encode_weather` added to the existing
`from src.features import ...` line. The raw dataset and existing tests were
not touched.

```python
def test_encode_weather_rejects_unknown_label():
    """An unseen weather label must raise, not become NaN and be silently
    deleted by a later dropna()."""
    series = pd.Series(["GOOD", "UNKNOWN"])
    with pytest.raises(ValueError, match="unmapped weather labels"):
        encode_weather(series)
```

#### Failing output after adding the test (fault still in place)

```
$ python -m pytest tests/test_leakage.py -q
........F                                                                [100%]
=================================== FAILURES ===================================
__________________ test_encode_weather_rejects_unknown_label ___________________

    def test_encode_weather_rejects_unknown_label():
        """An unseen weather label must raise, not become NaN and be silently
        deleted by a later dropna()."""
        series = pd.Series(["GOOD", "UNKNOWN"])
>       with pytest.raises(ValueError, match="unmapped weather labels"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests/test_leakage.py:89: Failed
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_encode_weather_rejects_unknown_label - Fai...
1 failed, 8 passed in 0.66s
```

#### Successful initial repair

The `if unknown: raise` block was restored, keeping the new test.

```
$ make test
python -m pytest tests/ -q
................                                                         [100%]
16 passed in 1.36s
```

`git diff -- src/features.py` was empty. **Agent repair turns for attempt 1: 1**
(one Edit restoring the block, then `make test` passing).

#### Attempt 2: fault reintroduced, detected by the hook

The same block was removed again, with the new test kept. This time the
PostToolUse hook detected the fault. Hook:
`${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh`. Stderr, verbatim:

```
PostToolUse:Edit hook blocking error from command: "${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh": [${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh]: Leakage tests failed after editing /Users/Acelynn/Downloads/bikeshare-open/src/features.py:
........F                                                                                                                                                                                                     [100%]
===================================================================================================== FAILURES ======================================================================================================
_____________________________________________________________________________________ test_encode_weather_rejects_unknown_label _____________________________________________________________________________________

    def test_encode_weather_rejects_unknown_label():
        """An unseen weather label must raise, not become NaN and be silently
        deleted by a later dropna()."""
        series = pd.Series(["GOOD", "UNKNOWN"])
>       with pytest.raises(ValueError, match="unmapped weather labels"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests/test_leakage.py:89: Failed
============================================================================================== short test summary info ==============================================================================================
FAILED tests/test_leakage.py::test_encode_weather_rejects_unknown_label - Failed: DID NOT RAISE ValueError
1 failed, 8 passed in 0.66s
```

#### Final repair

The block was restored a second time.

```
$ make test
python -m pytest tests/ -q
................                                                         [100%]
16 passed in 1.38s
```

`git diff -- src/features.py` was empty. **Agent repair turns for attempt 2: 1.**

### Agent repair turns summary

| Attempt | Detected by hook? | Repair turns |
|---------|-------------------|--------------|
| 1 (original suite) | No | 1 |
| 2 (strengthened suite) | Yes | 1 |

Attempt 1 also needed one extra turn to add the test, which is test work and
not a repair.

### Observation: detection without remediation

The hook detected the fault only after the tests were strengthened. Its
detection power is exactly the power of the tests it runs: with the original
8 tests it was silent, and with the new test it blocked the edit. Even when it
detected the fault, it did not undo the edit. The faulty code stayed in
`src/features.py` until the agent restored it in a later turn. The hook is a
detector, not a rollback.
