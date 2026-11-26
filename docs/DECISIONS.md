# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.

## Step 2 — Dataset Exploration (2026-11-24)

- Model used: Qwen3.5:9b via Ollama (`bikeshare-coder`), with a 65,536-token context window.
- Independently verified 728 rows, 18 columns, date range 2011-01-03 to 2012-12-31, and one missing date (2011-03-10).
- Agent correctly reported weather counts: GOOD (463), MISTY (245), BAD (20). Verified using pandas.
- Agent omitted six columns: `yr`, `mnth`, `temp`, `atemp`, `hum`, and `windspeed`. Verified all columns using `df.dtypes`.
- Agent incorrectly described numerical encodings for `season`, `holiday`, and `weekday`. Actual values are string labels, verified using `.unique()`.
- Agent initially used hardcoded calendar boundaries and failed to parse dates correctly. It later corrected the datetime error. Independently verified the missing date using `pd.date_range()` and `.difference()`.
- Agent incorrectly reported approximately 730 training observations. Actual split sizes are 362 training, 182 validation, and 184 testing.
- Agent correctly identified `casual` and `registered` as leakage but incorrectly suggested either alone guarantees near-perfect prediction. Verified that their sum equals `cnt` for every row.
- Agent initially misclassified `cnt_2d_bfr` as leakage. After questioning, it recognized that the column is excluded because its construction and alignment are unverified.
- Agent correctly explained why random splitting is inappropriate for forecasting.
- Agent attempted unavailable Explore tools, unnecessary subagents, and CSV validation using `py_compile`. Human intervention and smaller prompts were needed.
- Decision: independently verify agent-generated claims against the raw data before accepting them, even when the agent has access to the correct project instructions.

## Step 3 — Naive Modeling and Target Leakage (2026-11-24)

- Submitted the naive modeling prompt in a fresh Claude session without additional modeling instructions.
- Unlike the tutorial example, the agent followed the existing project pipeline and respected the standing leakage and temporal split constraints.
- Agent reported test R^2 scores of -2.14 for the mean baseline, 0.51 for persistence, 0.58 for ridge, and -0.50 for histogram gradient boosting.
- Persistence achieved a lower test MAE (840.1) than ridge (947.1), despite ridge having a higher R^2.
- Ran the provided deterministic experiment using `python -m src.leakage_demo`. Features were casual, registered, temp, and hum. Test R^2 was 1.000000.
- Agent initially attempted to calculate residuals using processed features and attempted to print an unnecessarily large table.
- After a more specific prompt, the agent attempted an incorrect SciPy implementation before using the requested NumPy least-squares method.
- Successfully computed the maximum absolute residual using numpy.linalg.lstsq on the raw CSV: 9.212e-12, confirming that casual and registered reconstruct cnt to floating-point precision.
- Decision: Treat unexpectedly high performance as a potential leakage warning and require numerical verification before accepting modeling results.
- Repository setup note: The initial starter commit was created retrospectively after tutorial Steps 2 and 3. I extracted a fresh copy of the original ZIP, compared it against my working project, committed the unmodified starter, and restored my tutorial notes.

## Step 4 — Rolling Standard Deviation (2026-11-24)

- Added cnt_roll_std_7 using shift(1) before rolling(7). All seven previous daily counts are available at prediction time. Existing seven-day warmup is sufficient. Validation R^2 improved for ridge from 0.6475 to 0.7224 (+0.0749) but declined for hgb from 0.2185 to 0.0977 (-0.1208). Retain the feature based on ridge exceeding the 0.01 improvement threshold, while documenting the decline in hgb.

## Process updates (2026-11-25)

- **Mandatory approval pause in `/seed-fault`.** The skill now stops after capturing the fault and test evidence and waits for explicit user approval before repairing. Rationale: the experiments needed the failure recorded while the fault was still in the working tree, and the hook only detects an edit and does not undo it, so repairing automatically would remove the state being studied. The pause is not counted as a repair turn.
- **`cnt_roll_std_7` rule added to `CLAUDE.md`.** The feature must use only the previous seven calendar days (`.shift(1)` before `.rolling(LAG_WARMUP).std()` on the gap-free index). Rationale: it was added in Step 4 with its own test, but the standing rules only named lag and rolling features in general, so the specific guarantee and its test were not written down where a future edit would see them.
- **Explicit raw-column classification rule added to `CLAUDE.md`.** New raw columns must be classified in `src/config.py` as `DATE_COL`, `FORBIDDEN`, or `ALLOWED_RAW_COLS`, enforced by `tests/test_contract.py`. Rationale: `feature_columns()` is a denylist, so an unclassified numeric column would become a feature with no test failing. Classification requires human review and does not itself prove an approved column is leakage-free.
- **`/seed-fault` and `/new-feature` listed in `CLAUDE.md`.** Rationale: so the skills and their intended use are visible in the standing project instructions. `/seed-fault` is for testing the verification suite, not for making real changes.

## Exercise 4 — Target transformation: hgb_delta (2026-11-25)

- Experiment: fit the existing booster on `cnt - cnt_lag_1` and reconstruct predictions as `cnt_lag_1 + predicted difference` (`LagDifferenceRegressor` in `src/train.py`, behind `--delta-hgb`; the default pipeline and `MODELS` are unchanged). Features, temporal splits, hyperparameters and the random seed are unchanged (the booster is cloned from `MODELS["hgb"]`). All metrics are on the original count scale. No leakage: the lag is the same-row `cnt_lag_1` column, known at prediction time.
- Acceptance criteria, fixed before the validation run: `hgb_delta` must (1) beat persistence on validation MAE and (2) improve validation R^2 over untransformed `hgb` by more than 0.01. Its validation R^2 and MAE are also compared with ridge to judge whether it is competitive.
- Actual validation results (`python -m src.train --delta-hgb --valid-only`, 182 validation days, saved in `reports/experiments/hgb_delta_valid.json`): hgb_delta R^2 0.5642 / MAE 885.8; hgb 0.0977 / 1381.6; persistence 0.4507 / 900.6; ridge 0.7224 / 700.4; mean baseline -0.9318 / 2002.2. hgb_delta vs hgb: R^2 +0.4665, MAE -495.8. vs persistence: R^2 +0.1135, MAE -14.8. vs ridge: R^2 -0.1582, MAE +185.4.
- Criteria check: both criteria are met. (1) 885.8 < 900.6. (2) +0.4665 > 0.01.
- Decision: adopt `hgb_delta` as an experimental model for Exercise 4. Ridge remains the strongest model on validation and is retained as the best model; `hgb_delta` is not competitive with it (lower R^2 by 0.158, higher MAE by 185).
- Rationale: differencing removes the 2011-to-2012 growth trend from the target, so the booster no longer has to predict counts above its 2011 training range; the lag carries the current level. This turns the booster from the worst model on validation into one that is slightly better than persistence.
- Caveat: the MAE improvement over persistence is small (14.8, about 1.6%). Statistical significance has not been established, and no interval was computed on 182 days. The larger R^2 gain over `hgb` is the stronger evidence. No tuning or iteration was done on validation: one run with fixed settings.
- Test protocol: the test set is scored once with `python -m src.train --delta-hgb --final-test`, after this entry. Results are saved separately in `reports/experiments/hgb_delta_test.json`; `reports/metrics.json` is not overwritten. The model will not be tuned or changed based on test results.

## Exercise 4 — Final test results and interpretation (2026-11-25)

The original validation-based adoption decision above is unchanged. This entry records what happened when the test set was scored once, with `python -m src.train --delta-hgb --final-test` (184 test days; saved in `reports/experiments/hgb_delta_test.json`). Nothing was tuned or modified after seeing these numbers, and the command was not re-run.

| Model | Test R^2 | Test MAE |
|---|---|---|
| baseline_mean | -2.1441 | 2847.7 |
| baseline_persistence | 0.5099 | 840.1 |
| ridge | 0.6356 | 840.3 |
| hgb | -0.6959 | 2108.4 |
| hgb_delta | 0.4761 | 990.5 |

- hgb_delta vs hgb: R^2 +1.1720, MAE -1117.9. vs persistence: R^2 -0.0338, MAE +150.4. vs ridge: R^2 -0.1595, MAE +150.2.
- Interpretation: differencing the target substantially improved the booster. Test R^2 went from -0.6959 to 0.4761 and MAE fell by about 1118, consistent with the explanation that a tree cannot predict counts above its 2011 training range while the difference target removes that growth trend.
- It did not outperform persistence on the held-out test set. It was worse on both R^2 (0.4761 vs 0.5099) and MAE (990.5 vs 840.1). The validation MAE edge over persistence (14.8, about 1.6%) did not hold on test, which fits the caveat recorded with the adoption decision that its significance was not established. Under the pre-set criteria, the first criterion (beat persistence on MAE) was met on validation and not met on test.
- Ridge remains the strongest model on validation and by test R^2. Its test MAE (840.3) is essentially tied with persistence (840.1); its advantage on test is in R^2.
- Decision: retain `hgb_delta` as an optional experimental model behind `--delta-hgb`, not a replacement for the default models. The default pipeline, `MODELS` and `reports/metrics.json` are unchanged. `hgb_delta` should not be presented as an improvement over persistence.
- Consistency check: the untransformed models in `reports/metrics.json` (baseline_mean, baseline_persistence, ridge, hgb) match the same models in `reports/experiments/hgb_delta_valid.json` and `hgb_delta_test.json` exactly, for R^2 and MAE on both splits, with the same feature list and split sizes (n_features 15, n_train 348, n_valid 182, n_test 184). `reports/metrics.json` has no `hgb_delta` entry, as intended.
- Repository: `.gitignore` no longer ignores `reports/` or `audit.jsonl`, so `reports/metrics.json`, `reports/experiments/` and the future `reports/audit.jsonl` can be tracked. Exclusions for processed data, virtual environments and caches are kept.

## Exercise 5 — Ridge vs persistence (2026-11-25)

- Decision: favor ridge over persistence when larger prediction errors are costly. Persistence remains a reasonable simpler alternative, since it needs no fitting and its test MAE is nearly identical to ridge's.
- Evidence (saved untransformed metrics in `reports/metrics.json`; no retraining, tuning, model-code change or metrics regeneration): validation (182 days) ridge R^2 0.7224 / MAE 700.4 vs persistence 0.4507 / 900.6; test (184 days) ridge R^2 0.6356 / MAE 840.3 vs persistence 0.5099 / 840.1.
- Rationale: test MAE is nearly identical (840.3 vs 840.1), but R^2 = 1 - SSE/SST measures squared error, which weights large misses far more than MAE. On the same test set, 1 - R^2 is 0.3644 for ridge and 0.4901 for persistence, which implies about 26% lower mean squared error (about 14% lower RMSE) for ridge. Ridge therefore has lower squared error at nearly identical MAE. The residual distribution was not examined directly, so this does not show how the difference arises or that ridge necessarily makes fewer large errors. Ridge also leads on both validation metrics.
- Caveat: one validation split and one test split, with no significance test or confidence interval. This does not establish significance or that ridge would outperform persistence in deployment.
- Verification: the full test suite passed after Exercise 4 (`make test`: 23 passed in 3.33s), covering the 18 earlier tests plus the 5 new Exercise 4 tests.

## Automated self-audit (2026-11-25)

- Ran the Agent SDK batch auditor (`agent/audit.py`) on this repository, after Exercises 4 and 5 and the final report. The first attempt, `python agent/audit.py . --out reports/audit.jsonl`, failed: the script defaults to the local `bikeshare-coder` model (`AUDIT_MODEL`), which only exists behind Ollama, and the Ollama configuration had been removed from the working-tree `.claude/settings.json` when switching to a hosted model. The error was "There's an issue with the selected model (bikeshare-coder). It may not exist or you may not have access to it."
- The successful command was `AUDIT_MODEL=claude-sonnet-5-5 python agent/audit.py . --out reports/audit.jsonl`, which printed `audited 1 repos; 0 flagged -> reports/audit.jsonl`. The audit was run once; the saved file is `reports/audit.jsonl`.
- Final verdict: `leakage: none`, `temporal_ok: true`, `baseline_reported: true`, `reproducible: true`, `confidence: high`.
- Finding 1 (`src/features.py`, line 55): same-day weather (`temp`, `atemp`, `hum`, `windspeed`, `weather_severity`) is measured on the day being predicted, so it is only legitimate if a weather forecast is available at prediction time. The audit states this is not target leakage (its identity check returned clean on all 15 features) but an assumption about what is known at prediction time. Response: recorded as a forecasting assumption in `README.md`; real-world performance may differ when forecasts replace observed weather.
- Finding 2 (`.claude/settings.json`, line 1): the working tree has an uncommitted edit that removes the local Ollama model and env configuration. The audit says this does not affect the pipeline or the metrics. Response: intentional (switch to a hosted model); the file is deliberately not committed.
- Effect on results: neither finding requires changing the current experimental results. Finding 1 limits how the results should be interpreted, and that limitation is acknowledged. Finding 2 concerns repository state only.
- Limits: the automated audit is a check by a model-driven tool. It does not prove the absence of all leakage, and its verdict is not a substitute for the leakage tests, the raw-column contract test, or human review.
