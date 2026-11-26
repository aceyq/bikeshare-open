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
