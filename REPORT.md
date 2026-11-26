## Results

| Feature version | Model | Validation R² | Validation MAE | Test R² | Test MAE |
|---|---|---|---|---|---|
| Before | Mean baseline | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| Before | Persistence baseline | 0.4507 | 900.6 | 0.5099 | 840.1 |
| Before | Ridge | 0.6475 | 832.9 | 0.5833 | 947.1 |
| Before | HGB | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| After | Mean baseline | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| After | Persistence baseline | 0.4507 | 900.6 | 0.5099 | 840.1 |
| After | Ridge | 0.7224 | 700.4 | 0.6356 | 840.3 |
| After | HGB | 0.0977 | 1381.6 | -0.6959 | 2108.4 |

"Before" is the 14-feature set (`docs/feature-metrics-before.json`) and "After" adds `cnt_roll_std_7`, 15 features (`reports/metrics.json`). Both runs use the same temporal splits and sample sizes: 348 training days (2011), 182 validation days (H1 2012) and 184 test days (H2 2012). The feature lists are identical apart from the added column, so the two versions are comparable. R² and MAE are on the original rental-count scale.

`cnt_roll_std_7` is the standard deviation of daily rentals over the previous seven calendar days (`.shift(1)` before `.rolling(7).std()` on the gap-free calendar), a measure of recent demand volatility that is known at prediction time. It needs no extra warm-up rows. The two baselines do not use it, so their rows are unchanged by construction.

On validation the effect was mixed. Ridge improved: R² rose from 0.6475 to 0.7224 (+0.0749) and MAE fell from 832.9 to 700.4 (-132.5, about 16%). HGB got worse: R² fell from 0.2185 to 0.0977 (-0.1208) and MAE rose from 1296.6 to 1381.6 (+85.0, about 7%). The test columns show the same directions, with ridge's R² up 0.0523 and MAE down 106.8, and HGB's R² down 0.1984 and MAE up 135.8. The feature was retained because ridge's validation gain exceeded the 0.01 threshold, and the HGB decline is documented, not hidden. We did not investigate why HGB declined. These are single validation and test splits with no significance testing.

## Headline finding

Ridership grew by about 63% from 2011 to 2012 (mean daily rentals 3,427 to 5,600 in the raw data), so models trained on 2011 are scored on days at a level they never saw. In the modelling table the mean daily count is 3,494 in training, 5,152 in validation and 6,043 in test. The average test day is about as busy as the busiest 2011 day (6,043), and 39% of validation days and 57% of test days exceed that 2011 maximum. A tree-based model predicts averages of training targets within its leaves, so it cannot extrapolate far beyond the range it was trained on. Ridge and persistence do not have this limit, because both take the current level from the lagged inputs.

The test metrics follow that pattern. HGB scored R² -0.6959 and MAE 2108.4, against 0.6356 and 840.3 for ridge and 0.5099 and 840.1 for persistence. A negative R² is a meaningful result, not a software bug: R² is 1 − SSE/SST measured against the test-set mean, so a negative value means the model's squared error is larger than that of a constant prediction at the test mean. HGB did worse than that constant, and the 2011-mean baseline did worse still (R² -2.1441), which shows how much the level shift alone costs. The same metric code, rows and splits give sensible positive values for ridge and persistence, and the test suite passes, which argues against a computation error, although it does not prove there is none.

This is a methodological explanation, not a proven causal finding. We did not run a diagnostic that isolates extrapolation, such as inspecting HGB's predictions against the 2011 target range. The Exercise 4 result below, where changing only the target raised HGB's test R² from -0.6959 to 0.4761, is consistent with the explanation but does not prove it.

## Exercise 4: target transformation

We fit HGB on the lag difference y_t = cnt_t − cnt_(t−1), taking cnt_(t−1) from the existing `cnt_lag_1` column of the same row, and reconstruct each prediction by adding yesterday's count back: ĉnt_t = ŷ_t + cnt_(t−1). Metrics are computed on the original rental-count scale. Features, temporal splits, hyperparameters and the random seed are unchanged, and the lag is known at prediction time, so there is no leakage. Differencing is intended to reduce the model's dependence on the absolute demand level: the booster models the change from yesterday, and the current level comes from the added lag instead of from the tree's leaves. We did not check whether the differenced targets cover similar ranges in the training and later periods. A model that always predicts a zero difference reproduces persistence exactly.

| Model | Validation R² | Validation MAE | Test R² | Test MAE |
|---|---|---|---|---|
| hgb_delta | 0.5642 | 885.8 | 0.4761 | 990.5 |
| HGB | 0.0977 | 1381.6 | -0.6959 | 2108.4 |
| Persistence | 0.4507 | 900.6 | 0.5099 | 840.1 |
| Ridge | 0.7224 | 700.4 | 0.6356 | 840.3 |

Relative to HGB, hgb_delta changed R² by +0.4665 and MAE by -495.8 on validation, and by +1.1720 and -1117.9 on test. Relative to persistence it changed validation R² by +0.1135 and MAE by -14.8, but test R² by -0.0338 and MAE by +150.4. Relative to ridge it was lower on both splits: validation R² -0.1582 and MAE +185.4, test R² -0.1595 and MAE +150.2.

The adoption criteria were set before the validation run: hgb_delta had to beat persistence on validation MAE and improve validation R² over untransformed HGB by more than 0.01, with ridge as a competitiveness check. It met both (885.8 against 900.6, and +0.4665), and it was not competitive with ridge. The MAE margin over persistence was small, about 1.6% on 182 days, and we did not establish its statistical significance. On the test set, scored once, it was worse than persistence on both metrics, so the validation advantage did not generalize; we did not investigate why. hgb_delta remains an optional experimental model behind `--delta-hgb`, not a replacement for the default pipeline, and `reports/metrics.json` is unchanged.

## Exercise 5: ridge vs persistence

On validation (182 days), ridge scored R² 0.7224 and MAE 700.4 against persistence's 0.4507 and 900.6. On test (184 days), ridge scored R² 0.6356 and MAE 840.3 against persistence's 0.5099 and 840.1. The test MAEs are nearly identical, but R² is 1 − SSE/SST, so it measures squared error, which penalizes large misses much more than MAE does. On the same test set, ridge's R² implies about 26% lower mean squared error than persistence (0.3644 versus 0.4901 of the total variance), or about 14% lower RMSE. Ridge therefore has lower squared error at nearly identical MAE; we have not examined the residual distribution directly, so this does not show how the difference arises or that ridge necessarily makes fewer large errors. We favor ridge when larger prediction errors are costly, while persistence remains a reasonable simpler alternative that needs no fitting and has a nearly identical test MAE. These are single validation and test splits with no significance testing or confidence intervals, so the comparison does not establish that ridge would outperform persistence in deployment.

## Attribution

**Agent-generated.** Claude Code implemented the `cnt_roll_std_7` feature and generated the subsequent tests and code changes, working from my instructions after the supplied starter snapshot. This includes the seeded-fault edits and repairs, the added tests (weather validation, raw-column contract, lag-difference wrapper), the `LagDifferenceRegressor` and its `--delta-hgb` flags, the custom `/seed-fault` skill, and the drafts of `docs/SEEDED_FAULTS.md`, `docs/DECISIONS.md` and this report. I did not manually write that code. The one exception is the original failing test for `cnt_roll_std_7` (commit `6ca2159`), which I entered manually with ChatGPT's guidance.

**Human decisions, made with AI assistance.** The methodological decisions were mine, but I made them with AI assistance, and not every experimental idea originated independently from me. ChatGPT helped me plan experiments, and Claude Code proposed the acceptance criteria for `hgb_delta`, which I adopted and extended with a comparison against ridge. I decided to add `cnt_roll_std_7` and to keep it despite its decline for HGB, the leakage-prevention requirements I added to the starter's rules (the explicit raw-column classification and the `cnt_roll_std_7` rule), whether to adopt `hgb_delta`, and to favor ridge over persistence when larger errors are costly.

**Human review and verification.** I approved each plan and repair before the agent proceeded, ran `make test` myself, and requested the verification runs recorded in the docs. I caught and had the agent correct its mistakes, including a misquoted hook result in Fault 5 (the hook reported 8 passed, not 7), overstated wording ("equal" MAE, a claim that ridge makes fewer large errors, an untested explanation for HGB's decline, and a claim about differenced target ranges), all of which were corrected. Corrections to the agent's earlier work are also noted in `docs/DECISIONS.md`.

**ChatGPT.** I used ChatGPT to interpret the assignment requirements, plan experiments, draft prompts, guide my manual entry of the original failing test, and review the agent's outputs.

**Models used.** The local `qwen3.5:9b` model (a 7.6 GB download), built as `bikeshare-coder` with a 65,536-token context window (`model/Modelfile`) and run through Claude Code, was used for the tutorial and Exercise 1. I switched to a hosted Claude model around the beginning of Exercise 2 because local inference was excessively slow. The commits from `fae388c` through `1cbae51` (2026-11-25) identify Claude Sonnet 5.5 in their co-author trailers. I cannot establish a more precise switch point than that.
