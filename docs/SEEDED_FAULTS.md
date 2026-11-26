# Seeded faults (MA6 Exercise 2)

Controlled fault-injection experiments. For each fault, a deliberate edit was made with Claude Code, the PostToolUse hook and the test suite were observed, and the fault was repaired after my approval. Roles and models are described in the Attribution section of `REPORT.md`.

| Fault | Edit | Hook outcome | Repair turns |
|---|---|---|---|
| 1 | `casual` allowed into `feature_columns()` | detected (`test_no_forbidden_features`) | 1 |
| 2 | `.shift(1)` removed from `cnt_roll_7` | detected (`test_rolling_mean_excludes_today`) | 1 |
| 3 | weather label validation removed | silent at first (8 passed in 0.47s); detected after a new test was added | 1 per attempt |
| 4 | Bash copy into `data/raw/` | not executed: denied by the permission layer, so no hook ran | n/a |
| 5 | `.shift(1)` removed from `cnt_roll_std_7` | detected (`test_rolling_std_excludes_today`) | 1 |

In every detected case the hook reported the failure but did not undo the edit.

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

The hook detected the edit but did not undo it; the fault stayed in the file until it was repaired in a later turn.

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

The hook detected the edit but did not undo it; the fault stayed in the file until it was repaired in a later turn.

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

## Fault 4: Bash copy into `data/raw/` (attempted, denied)

**Intended experiment:** show that the `Edit|Write` PostToolUse hook cannot
detect a Bash copy into `data/raw/`.

**Actual outcome:** the experiment did not complete. Both copy attempts were
denied by the permission layer and never executed. **No copy was made, and no
leakage hook ran.** This section does not claim a successful copy. What the
hook can and cannot see is argued below from the configuration, not from an
observed run.

### Commands attempted

Pre-checks (these ran):

```
shasum -a 256 data/raw/bike_daily.csv
ls -la data/raw/
```

The check that `data/raw/seeded_fault_copy.csv` did not already exist also
ran, and it did not exist.

Attempt 1 (Bash tool). This differs from the requested command: a
`; echo "cp exit code: $?"` suffix was appended to capture the exit status.

```
cp -n data/raw/bike_daily.csv data/raw/seeded_fault_copy.csv; echo "cp exit code: $?"
```

Attempt 2 (Bash tool). The exact requested command, with no suffix:

```
cp -n data/raw/bike_daily.csv data/raw/seeded_fault_copy.csv
```

### Permission denial output (verbatim)

Attempt 1:

```
Permission to use Bash with command cp -n data/raw/bike_daily.csv data/raw/seeded_fault_copy.csv; echo "cp exit code: $?" has been denied.
```

Attempt 2:

```
Permission to use Bash with command cp -n data/raw/bike_daily.csv data/raw/seeded_fault_copy.csv has been denied.
```

- **Attempt 1:** the user reports manually approving this command, but it was
  still denied. The agent did not see an approval prompt; it only received the
  denial.
- **Attempt 2:** denied by the permission layer without executing. The agent
  saw no approval prompt.

### State verification

Run just before writing this section:

```
$ ls -la data/raw/
total 176
drwxr-xr-x@ 3 Acelynn  staff     96 Nov 10 09:52 .
drwxr-xr-x@ 4 Acelynn  staff    128 Nov 10 09:52 ..
-rw-r--r--@ 1 Acelynn  staff  86325 Nov 10 09:52 bike_daily.csv

$ git status --short
 M .claude/settings.json

$ shasum -a 256 data/raw/bike_daily.csv
a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc  data/raw/bike_daily.csv
```

- **Original CSV hash before:** `a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc`
- **Original CSV hash after:** `a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc`
  (unchanged)
- **Temporary copy exists:** no. `data/raw/seeded_fault_copy.csv` is absent
  and `data/raw/` holds only `bike_daily.csv`.
- **Leakage hook:** did not run, because neither copy executed.

### Configuration inspected

`.claude/settings.json` (working-tree version, which has uncommitted
changes relative to `HEAD`):

```json
"hooks": {
  "PostToolUse": [
    { "matcher": "Edit|Write",
      "hooks": [ { "type": "command",
                   "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh",
                   "timeout": 60 } ] }
  ]
},
"permissions": {
  "allow": [ "Bash(make:*)", "Bash(python -m pytest:*)", "Bash(python -m src.:*)",
             "Bash(git diff:*)", "Bash(git status)" ],
  "deny":  [ "Write(./data/raw/**)", "Edit(./data/raw/**)", "Bash(rm -rf:*)" ]
}
```

### Observed: the permission denial

The denials above are real and observed. The configuration does **not**
explain them:

- No `deny` rule matches a Bash `cp`. The deny list covers `Write` and `Edit`
  on `data/raw/**`, plus `Bash(rm -rf:*)`.
- `cp` is not in the `allow` list, so it needs interactive approval. The
  user's approval did not take effect.

The actual cause of the denial is therefore **unknown**. It could come from
another settings layer, the session's permission mode, or how the approval
was relayed. The inspected files do not show it. The observed protection is
in the permission layer, not in `settings.json` rules as written.

### Theoretical: why the hook does not monitor Bash

This part follows from reading the configuration and hook script. It was not
observed in a run.

1. **Matcher.** The PostToolUse matcher is `Edit|Write`. A Bash tool call
   does not match it, so `check_leakage.sh` would not be invoked for a
   Bash `cp`.
2. **Script filter.** Even if invoked, `check_leakage.sh` reads
   `tool_input.file_path` from the payload. A Bash payload has a `command`
   field and no `file_path`, so `path` would be empty. The `case` statement
   only continues for `*src/*.py`, so any other path takes `exit 0`.
3. **Scope.** The script only re-runs `tests/test_leakage.py` when a `src/`
   Python file changes. It never looks at `data/raw/`.
4. **Timing.** It is a PostToolUse hook, so it runs after the change has
   landed. At best it could report a problem after the fact, not prevent it.
5. **Deny rules.** The `Write`/`Edit` deny rules for `data/raw/**` only govern
   those tools. They do not cover a Bash `cp`, `mv`, redirection or
   `python -c` write.

In short, a Bash copy into `data/raw/` is outside both the hook's matcher and
the deny rules as written. In this experiment that gap was never exercised,
because the copy was blocked before it ran.

### Additional protections

- **PreToolUse Bash hook.** A hook with matcher `Bash` runs before the
  command and can exit 2 to block it. It would inspect `tool_input.command`
  and reject writes that target `data/raw/` (`cp`, `mv`, `>`, `tee`,
  `sed -i`, `dd`). Pattern matching on shell strings is best-effort and can be
  bypassed with indirection, so it should be one layer among several.
- **Filesystem permissions.** Making `data/raw/` and `bike_daily.csv`
  read-only (for example `chmod a-w`) stops any writer, including Bash,
  Python and the Edit/Write tools, at the OS level. `cp -n` creating a new
  file would need a non-writable directory to be blocked. The weakness is that
  the owner can undo it with `chmod`. Running the agent under a different
  user, or a read-only mount, is stronger. No permissions were changed in this
  experiment.
- **Raw-data integrity check.** Record the SHA-256 of
  `data/raw/bike_daily.csv`, and assert that `data/raw/` contains exactly the
  expected files, in `make data` or a test. This catches changes to the
  original and stray extra files after the fact. It does not prevent them, and
  the existing shape assertion in `make data` does not check for extra files.
  It is cheap and independent of how the file was written.

### Observation

The existing hook is a detector for `src/` edits made through Edit and
Write. It has no view of Bash, and it does not undo anything. In Fault 4 the
only thing standing between the agent and a write into `data/raw/` was the
permission layer, whose cause for denying the command is not visible in the
repository configuration.

## Additional raw-column contract test

Not a seeded fault. Written after Faults 1-4 to close a gap seen in the
design: `feature_columns()` is a denylist (every numeric column not in
`FORBIDDEN`), so a new numeric column in the raw CSV would become a model
feature with no test failing. `REQUIRED_COLS` in `src/ingest.py` only
checks that columns are present, not that extra ones are rejected.

### Test design

Raw columns are classified explicitly in `src/config.py`. Nothing is
inferred from dtypes.

```python
FORBIDDEN = LEAKAGE_COLS | TIME_INDEX_COLS | UNVERIFIED_COLS  # existing
DATE_COL = "dteday"
ALLOWED_RAW_COLS = {
    "season", "mnth", "holiday", "weekday", "workday", "weather",
    "temp", "atemp", "hum", "windspeed",
}
```

Two tests were added to `tests/test_contract.py`:

```python
def test_every_raw_column_is_explicitly_classified():
    header = set(pd.read_csv(RAW, nrows=0).columns)
    unclassified = header - ALLOWED_RAW_COLS - FORBIDDEN - {DATE_COL}
    assert not unclassified, (
        f"unclassified raw columns: {sorted(unclassified)}; classify each in "
        "src/config.py as ALLOWED_RAW_COLS or FORBIDDEN"
    )

def test_raw_column_classes_are_disjoint():
    assert not (ALLOWED_RAW_COLS & FORBIDDEN)
    assert DATE_COL not in ALLOWED_RAW_COLS | FORBIDDEN
```

The header is read directly from the file with `nrows=0`. A column that is
in none of the three sets fails the test, whatever its dtype. The
disjointness test stops a column from being listed in two classes (for
example `casual` in both) to satisfy the first test. The existing
`feature_columns()`, the other tests and the hook configuration were not
changed. The only edit to existing code is the `src.config` import line in
`tests/test_contract.py`.

### Classification of the 18 raw columns

| Class | Columns |
|---|---|
| Date (1) | `dteday` |
| Forbidden (7) | `casual`, `registered`, `cnt` (leakage); `instant`, `yr`, `days_since_2011` (time index); `cnt_2d_bfr` (unverified) |
| Allowed raw (10) | `season`, `mnth`, `holiday`, `weekday`, `workday`, `weather`, `temp`, `atemp`, `hum`, `windspeed` |

A script check confirmed that every one of the 18 header columns is in
exactly one class, that there are no unclassified columns, and that there are
no stale entries (classified names missing from the CSV).

### Passing output

```
$ make test
python -m pytest tests/ -q
..................                                                       [100%]
18 passed in 1.39s
```

The 18 tests are the previous 16 plus the 2 new contract tests.

### Failing output: temporary `leak_proxy` experiment

To show the actual test fails on an unclassified column, a scratch pytest
file outside the repository (in the session scratchpad) did the following:

1. Read the original raw CSV, without writing to it.
2. Added a column `leak_proxy = registered * 0.5` and wrote the result to
   pytest's `tmp_path`, outside `data/raw/`.
3. Used `monkeypatch.setattr` to point the `RAW` name in the loaded
   `tests/test_contract.py` module at the temporary CSV.
4. Called the real `test_every_raw_column_is_explicitly_classified`.

Result:

```
E       AssertionError: unclassified raw columns: ['leak_proxy']; classify each in src/config.py as ALLOWED_RAW_COLS or FORBIDDEN

tests/test_contract.py:68: AssertionError
FAILED ...demo_leak_proxy.py::test_contract_fails_on_unclassified_column
1 failed in 1.06s
```

The scratch file is not part of the repository and was not committed.

### Original CSV hash

`data/raw/bike_daily.csv` SHA-256 before the changes, after the
`leak_proxy` experiment, and again just before this commit:

```
a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc
```

The hash is unchanged. The original was never modified, even temporarily.
`data/raw/` still contains only `bike_daily.csv`.

### What this does and does not prove

Explicit classification requires human review. It does not independently
prove that an approved column is leakage-free.

- The test only forces a person to put each raw column in a class. It cannot
  tell whether a column is leaky.
- Someone can add a leaky column to `ALLOWED_RAW_COLS`, and the test will
  pass. What protects against that is the review of the diff to
  `src/config.py`, guided by the comment there: check that the column is
  not a restatement of `cnt` and is known at prediction time.
- It checks only the raw CSV header. Derived columns built in
  `build_features` are covered by `tests/test_leakage.py`.
- `feature_columns()` is still a denylist. A stronger follow-up would make
  it an allowlist, which was not done here.

## Fault 5: `.shift(1)` removed from `cnt_roll_std_7` (additional custom skill verification)

Additional custom skill verification. This fault was seeded by invoking the
new `/seed-fault` skill (`.claude/skills/seed-fault/SKILL.md`) with the
argument "Remove .shift(1) from cnt_roll_std_7 in src/features.py so the
rolling standard deviation incorrectly includes today's demand." It checks
that the skill's workflow, including the mandatory approval pause, runs as
written. It is not one of the original Exercise 2 faults.

**File:** `src/features.py`, function `build_features()`, line 77

**Original line:**

```python
    out["cnt_roll_std_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).std()
```

**Faulty line (the seeded fault):**

```python
    out["cnt_roll_std_7"] = out[TARGET].rolling(LAG_WARMUP).std()
```

Only this line changed. `cnt_roll_7`, the other features and the tests were
untouched.

### Baseline (step 1)

```
$ git status --short
 M .claude/settings.json
 M CLAUDE.md
 M docs/DECISIONS.md
?? .claude/skills/seed-fault/

$ make test
python -m pytest tests/ -q
..................                                                       [100%]
18 passed in 1.64s
```

`src/features.py` had no uncommitted changes. The other uncommitted files
were not part of this experiment. Raw CSV SHA-256 before:
`a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc`.

### PostToolUse hook stderr (verbatim)

Hook: `${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh`, triggered by the Edit tool.

```
PostToolUse:Edit hook blocking error from command: "${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh": [${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh]: Leakage tests failed after editing /Users/Acelynn/Downloads/bikeshare-open/src/features.py:
        assert "cnt_roll_std_7" in feature_columns(feats)
    
        by_date = load_raw().set_index("dteday")[TARGET]
        checked = 0
    
        for date, actual in feats.set_index("dteday")["cnt_roll_std_7"].items():
            window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
            expected = by_date.loc[window].std()
>           assert actual == pytest.approx(expected), f"bad rolling std at {date}"
E           AssertionError: bad rolling std at 2011-01-10 00:00:00
E           assert 324.1362882081137 == 324.0354918832195 ± 3.2e-04
E             
E             comparison failed
E             Obtained: 324.1362882081137
E             Expected: 324.0354918832195 ± 3.2e-04

tests/test_leakage.py:79: AssertionError
============================================================================================== short test summary info ==============================================================================================
FAILED tests/test_leakage.py::test_rolling_std_excludes_today - AssertionError: bad rolling std at 2011-01-10 00:00:00
1 failed, 8 passed in 0.31s
```

The hook shows only the last 20 lines of pytest output (`tail -20` in the
script), which is why the traceback starts partway through the test.

### Failing test output (direct run, fault still in place)

Run during the approval pause:

```
$ python -m pytest tests/test_leakage.py -q
.......F.                                                                [100%]
=================================== FAILURES ===================================
_______________________ test_rolling_std_excludes_today ________________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7
0   2011-01-10     10.0  WINTER  ...     1...857     887.135250
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571     941.177353

[714 rows x 29 columns]

    def test_rolling_std_excludes_today(feats):
        """Rolling std must use only the previous seven calendar days."""
        assert "cnt_roll_std_7" in feature_columns(feats)

        by_date = load_raw().set_index("dteday")[TARGET]
        checked = 0

        for date, actual in feats.set_index("dteday")["cnt_roll_std_7"].items():
            window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
            expected = by_date.loc[window].std()
>           assert actual == pytest.approx(expected), f"bad rolling std at {date}"
E           AssertionError: bad rolling std at 2011-01-10 00:00:00
E           assert 324.1362882081137 == 324.0354918832195 ± 3.2e-04
E             
E             comparison failed
E             Obtained: 324.1362882081137
E             Expected: 324.0354918832195 ± 3.2e-04

tests/test_leakage.py:79: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_std_excludes_today - AssertionErro...
1 failed, 8 passed in 0.51s
```

The test failed at the first row it checks, 2011-01-10. Obtained
`324.1362882081137`, expected `324.0354918832195 ± 3.2e-04`. No test was added
or changed: the existing `test_rolling_std_excludes_today` detected the
fault. Whitespace on blank lines in the pasted block may differ from the
raw terminal output.

### Discrepancy: "7 passed" vs "8 passed"

During the approval pause, the agent's summary quoted the hook's result line
as `1 failed, 7 passed` while also saying `1 failed, 8 passed`. This was an
error by the agent, not a difference between the hook and a direct run.

- The hook's actual last line was `1 failed, 8 passed in 0.31s`.
- The agent's first write-up of the hook stderr wrongly said
  `1 failed, 7 passed in 0.31s`, and then described a mismatch that did not
  exist.
- `tests/test_leakage.py` now collects 9 tests (8 original plus
  `test_encode_weather_rejects_unknown_label`), so `1 failed, 8 passed` is
  correct. The earlier faults 1 and 2 reported 7 passed because the file then
  had 8 tests.
- The hook and the direct run differ only in time (0.31s and 0.51s).

No existing tests were changed to resolve the discrepancy.

### Approval pause

After capturing the evidence, the skill stopped with the fault still in the
working tree and asked for approval (step 6). The user approved the repair
and asked first for the direct run above.

### Successful repair

`.shift(1)` was restored with the Edit tool, then `make test`:

```
$ make test
python -m pytest tests/ -q
..................                                                       [100%]
18 passed in 1.87s
```

`git diff -- src/features.py` was empty. Raw CSV SHA-256 after:
`a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc`
(unchanged, and `data/raw/` still contains only `bike_daily.csv`).

### Agent repair turns

1. **Repair turns: 1.** The restore Edit and the passing `make test` happened
   in the one turn after approval. In the same turn the agent first ran the
   requested direct test run and investigated the discrepancy; that
   verification was not repair work.
2. The seeding turn (baseline, edit, evidence capture) was separate and is
   not counted as repair.

### Why removing `shift(1)` causes temporal leakage

`rolling(7).std()` on its own covers rows t-6 through t, so the window
includes the current day's `cnt`, the target being predicted. The feature
then carries part of the answer, and validation and test scores look better
than a real forecast could achieve. `.shift(1)` moves the series back one day
first, so the window covers t-7 through t-1 only. This matches the rule in
`CLAUDE.md` and the Fault 2 explanation for `cnt_roll_7`.

### Observation: detection without remediation

The hook detected the edit but did not undo it; the faulty line stayed in `src/features.py` until it was restored after approval. Unlike Fault 3, the existing suite already covered this behaviour, so the hook fired on the first attempt.
