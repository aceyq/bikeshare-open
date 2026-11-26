## Results

## Headline finding

## Exercise 4: target transformation

## Exercise 5: ridge vs persistence

On validation (182 days), ridge scored R² 0.7224 and MAE 700.4 against persistence's 0.4507 and 900.6. On test (184 days), ridge scored R² 0.6356 and MAE 840.3 against persistence's 0.5099 and 840.1. The test MAEs are nearly identical, but R² is 1 − SSE/SST, so it measures squared error, which penalizes large misses much more than MAE does. On the same test set, ridge's R² implies about 26% lower mean squared error than persistence (0.3644 versus 0.4901 of the total variance), or about 14% lower RMSE. Ridge therefore has lower squared error at nearly identical MAE; we have not examined the residual distribution directly, so this does not show how the difference arises or that ridge necessarily makes fewer large errors. We favor ridge when larger prediction errors are costly, while persistence remains a reasonable simpler alternative that needs no fitting and has a nearly identical test MAE. These are single validation and test splits with no significance testing or confidence intervals, so the comparison does not establish that ridge would outperform persistence in deployment.

## Attribution
