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
