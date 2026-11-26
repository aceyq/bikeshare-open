# Exercise 3: audit of a teammate's repository

- **Repository audited:** https://github.com/YadushanUCSD/DSC180A-Methodology-6
- **Commit audited:** `ebb4979` (HEAD at the time of the audit, 2026-11-25)
- **Auditor:** the `leakage-auditor` subagent defined in `.claude/agents/leakage-auditor.md`, run through Claude Code against a read-only local clone.
- **Scope:** the repository has no single diff, so the auditor reviewed the whole modelling pipeline at that commit (`src/config.py`, `features.py`, `train.py`, `ingest.py`, the tests, and the reported metrics files) against its five checks.
- **Constraint I added:** the repository is third-party code, so I told the auditor not to execute anything from it. It read the code and ran its own standalone checks on the repository's data files. As a result, the teammate's ridge and HGB scores were not independently reproduced, as the auditor also states.

## 1. Original auditor output (verbatim)

The text between the rules below is the subagent's output, unedited. File paths in it point to the local clone used for the audit. Everything after the second rule is my own review.

---

**Findings: two (one changes a reported number, one affects a conclusion). The remaining checks pass.**

**Finding 1 (check 5). The "baseline_mean" in the ratio experiment is not a mean baseline, and it beats the real models.**
- Location: `/private/tmp/claude-501/-Users-Acelynn-Downloads-bikeshare-open/c3a82e99-ffff-4f42-b332-b27938408cdd/scratchpad/teammate-repo/src/train.py` lines 104-111, which produces `reports/metrics_ratio.json` lines 24-28.
- Scenario: `scaled` is true for every model except `PersistenceBaseline`, so `DummyRegressor` is fit on `cnt/cnt_roll_7`. It predicts the mean ratio (1.015), and line 111 multiplies that by `cnt_roll_7`. The result is a rescaled 7-day-average forecast, not "predict the 2011 mean". It is saved under the key `baseline_mean` with valid R² 0.5947 and MAE 807.3. The true mean baseline is R² -0.9318 and MAE 2002.2, as in `reports/metrics.json`.
- Effect: a reader of `metrics_ratio.json` sees a "mean baseline" at 0.5947 that beats ridge (0.3905) and persistence (0.4507). It also sits only 0.158 R² below the ratio hgb (0.7527). That makes the ratio hgb gain look like "ratio-scaling plus a model". The numbers show most of the gain over persistence comes from using the trailing mean alone.
- Evidence (standalone computation in my own scratch directory, reading only the raw CSV):
  - n_train = 348 and n_valid = 182 reproduce.
  - Persistence R² 0.4507 and MAE 900.6 reproduce.
  - The raw mean baseline reproduces at -0.9318 and 2002.2.
  - The ratio-mean predictor reproduces at 0.5947 and 807.3.
  - Using `cnt_roll_7` directly as the forecast gives R² 0.5945.
- Minimal fix: in ratio mode, never rescale `baseline_mean`, so it stays a true mean baseline. Report `cnt_roll_7` as a separate third baseline named something like `baseline_roll7`. The ratio hgb (0.7527) should be compared against `baseline_roll7` (about 0.5945), not against persistence alone.

**Finding 2 (the test split was consulted for a model choice).**
- Location: `docs/DECISIONS.md` line 18, documenting the ratio path in `src/train.py` (lines 97-99).
- Scenario: the ratio target was adopted after hgb failed on validation and the test set was then consulted. The notes report hgb test R² 0.6247 and MAE 831.2, and ridge ratio test R² 0.0257. None of these numbers is in a committed metrics file, so the reported ratio-test figures are unreproducible from the repo's reports. This breaks the "never tune on test" rule in `CLAUDE.md`. The notes do admit the choice came after seeing hgb fail.
- Effect: the hgb "0.62 on test" figure is not clean held-out evidence. Pair it with Finding 1 when drawing any conclusion, since `baseline_roll7` was never scored on test.
- Minimal fix: either write the ratio test metrics to a file with the roll-7 baseline included and label them as post-selection, or drop the test claim.

**Checks that pass**
- **Check 1, target leakage:** `feature_columns` excludes `casual`, `registered`, `cnt`, `cnt_2d_bfr`, `instant`, `yr` and `days_since_2011`. The 15 features in both metrics files contain no restatement of the target. `cnt_lag_1`, `cnt_lag_2`, `cnt_lag_7` and `cnt_roll_7` are all strictly past values. The ratio denominator `cnt_roll_7` is a shifted mean, so it is known at prediction time.
- **Check 2, temporal ordering:** `cnt_roll_7` is `shift(1).rolling(7)`. The split in `temporal_split` is by date. `StandardScaler` sits inside a pipeline that is fit on train only. `DummyRegressor` is fit on train only. The ratio path fits on train only and scores validation only.
- **Check 3, calendar gaps:** `reindex_to_calendar` runs before the lags are built. Its row accounting reproduced in my own calculation, giving 348 train rows and 182 validation rows.
- **Check 4, silent row loss:** `encode_weather` raises on unknown labels. `test_only_expected_rows_are_dropped` bounds the loss at 14 rows, and the actual loss is 728 - 714 = 14. This bound lives in a test, not in `build_features`, which is acceptable.
- **Check 5, baselines in the raw path:** the mean baseline and persistence are both reported next to every model in `reports/metrics.json`. The only gap is Finding 1 in the ratio file.

**How each check was verified**
- By reading only: check 1 (feature list and `config.py` logic), the scaler and pipeline fit scope in check 2, and the `encode_weather` guard in check 4.
- By standalone computation: the shift(1) plus calendar reindex, the split sizes, the persistence and raw mean baselines, and the mislabeled ratio baseline (Finding 1). I did not retrain ridge or hgb, so their reported scores are unverified.

Scratch script: `/private/tmp/claude-501/-Users-Acelynn-Downloads-bikeshare-open/c3a82e99-ffff-4f42-b332-b27938408cdd/scratchpad/chk/c.py`. I executed nothing from the repository.

---

## 2. My review and verdict

The checks below were run with Claude Code under my direction. The conclusions are mine.

**Finding 1 (ratio-mode `baseline_mean`): accepted as a baseline reporting issue.** In `src/train.py`, ratio mode fits every model except persistence on `cnt / cnt_roll_7` and multiplies its predictions by `cnt_roll_7`. The `DummyRegressor` therefore becomes a rescaled trailing-mean forecast, but it is saved under the key `baseline_mean`. I reproduced the figures on my own project's validation split (348 training and 182 validation days, the same dataset):

| Predictor | Validation R² | Validation MAE |
|---|---|---|
| Mean training ratio × `cnt_roll_7` (their ratio-file `baseline_mean`) | 0.5947 | 807.3 |
| `cnt_roll_7` used directly | 0.5945 | 823.9 |
| True mean baseline (training mean of `cnt`) | -0.9318 | 2002.2 |

The first row matches `reports/metrics_ratio.json` exactly. The numbers are correct for what they compute, and this is not leakage, so the label is the problem. The committed default `reports/metrics.json` has the true mean baseline and is unaffected.

I correct one claim in the auditor's text. It says most of the improvement over persistence comes from the rolling mean. The ratio HGB improves validation R² over persistence by 0.7527 − 0.4507 = 0.302, and the rolling mean alone accounts for 0.5945 − 0.4507 = 0.144 of that, approximately 48%. That is about half, not most. The fix is to keep `baseline_mean` as a true mean baseline and report a rolling-mean baseline separately, so the ratio HGB is compared with it.

**Finding 2 (test set consulted for a model choice): partially accepted.** The legitimate concern is reproducibility. The ratio-mode test results (HGB 0.6247, MAE 831.2; ridge ratio 0.0257) appear only in prose in the teammate's `docs/DECISIONS.md`. The currently committed evaluation command (`python -m src.train --target ratio`) scores validation only, so it cannot reproduce those test numbers, and the order of events is self-reported (code and notes were committed together).

I do not accept that test-set tuning is established. The notes describe a choice made on validation results (HGB 0.2481 to 0.7527), followed by one test evaluation "after this choice", and they disclose both that the choice followed seeing HGB fail and that the validation-to-test drop (0.75 to 0.62) suggests some optimism. Selecting on validation and then looking at test once is the intended protocol. Missing committed test metrics do not show that test results influenced the choice.

**Test-set exposure in both projects.** The default pipeline writes test metrics for every model into the committed `reports/metrics.json`, in both projects. In both, the raw HGB's failure on test was visible before the target-transformation experiment, so neither project had a completely untouched test set. My own Exercise 4 was motivated by that same failure, and I scored the test set once after validation-based adoption. I consider the teammate's protocol comparable to mine on this point, and I do not claim either is free of exposure.

**What I did not verify.** I did not execute the teammate's pipeline, so I did not reproduce their ridge or HGB scores. I read their `src/train.py`, metrics files and `docs/DECISIONS.md`, and I reproduced only the baseline figures in the table above. I did not independently re-check the auditor's passes on checks 1 to 4 beyond that reading.
