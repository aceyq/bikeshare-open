# Bikeshare demand capstone

Daily Capital Bikeshare counts, 2011-2012. We forecast `cnt` (total daily
rides) from calendar, weather, and lagged-demand features.

## Commands
- `make data` - download raw CSV and assert its shape
- `make features` - build `data/processed/features.parquet`
- `make train` - fit models, write `reports/metrics.json`
- `make test` - pytest; run this before claiming anything works
- `make all` - the three pipeline stages in order

## Non-negotiable rules
- **Never** put `casual` or `registered` in a feature set:
  `casual + registered == cnt` exactly. `src/config.py` lists these and the
  other excluded columns (`cnt_2d_bfr`, raw time indexes) with the reason
  for each. Derive feature lists from `FORBIDDEN`; never hand-type them.
- **Never** split this data randomly. Use `src.train.temporal_split`.
  Train = 2011, valid = H1 2012, test = H2 2012. Never tune on test.
- Any new lag or rolling feature must be built on a gap-free calendar
  index (`src.features.reindex_to_calendar`) and must `.shift(1)` before
  it aggregates. Add a test for it in `tests/test_leakage.py`.
- Report the mean baseline **and** the persistence baseline (yesterday's
  count) alongside every model. A negative R^2 is a finding, not a bug
  to hide.
- `cnt_roll_std_7` must use only the previous seven calendar days:
  `.shift(1)` first, then `.rolling(LAG_WARMUP).std()`, on the gap-free
  index. `test_rolling_std_excludes_today` guards it; never weaken it.
- Every raw CSV column must be explicitly classified in `src/config.py`:
  `DATE_COL`, `FORBIDDEN`, or `ALLOWED_RAW_COLS`. Never infer it from
  dtype. `tests/test_contract.py` fails on an unclassified column. Adding
  to `ALLOWED_RAW_COLS` needs a human leakage review: not a restatement of
  `cnt`, and known at prediction time.

## Skills
- `/seed-fault <fault>` - fault-injection experiment. Seeds one fault with
  Edit so the hook runs, captures the evidence, **pauses for your explicit
  approval**, repairs, verifies, and appends to `docs/SEEDED_FAULTS.md`.
  Use it to test whether the suite and hook catch a fault, never to make a
  real change. It does not commit.
- `/new-feature <feature>` - add a predictor with its leakage test.

## Style
- Standard library, pandas, scikit-learn only. No new dependencies
  without asking. Versions are pinned in `requirements.txt`.
- Modules are runnable: `python -m src.<module>` prints a one-line `OK ...`
  summary.
- Paths and constants live in `src/config.py`. Nothing is hardcoded twice.

## Gotchas
- The mirror in `DATA_URL` is missing 2011-03-10. It is NOT the UCI file:
  728 rows from 2011-01-03, not 731 from 2011-01-01.
- `weather` uses the labels `GOOD` / `MISTY` / `BAD`, not the UCI codes 1-4.
- Ridership grew ~65% from 2011 to 2012, so tree models trained on 2011
  cannot extrapolate to 2012. That is the headline result, not an error.
- 2012-10-29 (Hurricane Sandy, 22 rides) is in the test set. Expect it in
  any residual plot.
