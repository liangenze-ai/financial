# Quant Stock Diagnosis API Contract

## Endpoint

`GET /api/quant/stock-diagnosis/`

This endpoint returns a model-based stock diagnosis for one stock on one trade date.
It is intended for inspection and product integration, not as an investment recommendation.

## Query Parameters

| Name | Required | Default | Description |
| --- | --- | --- | --- |
| `ts_code` | yes |  | TuShare stock code, for example `001390.SZ`. |
| `trade_date` | yes |  | Trade date formatted as `YYYYMMDD`, for example `20260401`. |
| `target` | no | `all` | `all`, `up`, or `outperform`. |
| `feature_version` | no | `v1` | Feature version in `model_sample_v1`. |

## Default Model Configuration

Configured through environment variables:

| Env var | Default |
| --- | --- |
| `QUANT_STOCK_DIAGNOSIS_PRIMARY_ARTIFACTS_DIR` | `artifacts/quant_baseline_medium_quality_value_ablate_calibrated` |
| `QUANT_STOCK_DIAGNOSIS_FALLBACK_ARTIFACTS_DIR` | `artifacts/quant_baseline_medium_no_momentum_quality_value_calibrated` |
| `QUANT_STOCK_DIAGNOSIS_SWITCH_MONTHS` | `202604` |

## Example Request

```text
GET /api/quant/stock-diagnosis/?ts_code=001390.SZ&trade_date=20260401
```

## Combined Response Shape

When `target=all`, the response contains:

```json
{
  "ts_code": "001390.SZ",
  "stock_name": "example",
  "industry": "example",
  "trade_date": "20260401",
  "feature_version": "v1",
  "model_role": "fallback",
  "use_fallback": true,
  "combined_signal": {
    "label": "strong_positive",
    "description": "Both absolute upside and relative outperformance scores are high.",
    "up_score_pct_rank": 1.0,
    "outperform_score_pct_rank": 0.9981,
    "up_decile": 10,
    "outperform_decile": 10,
    "confidence": "medium",
    "decile_gap": 0
  },
  "warnings": [],
  "targets": {
    "up": {
      "score": 0.56,
      "score_pct_rank": 1.0,
      "score_decile": 10,
      "cohort": "top",
      "observed": {
        "future_ret_20": 0.004,
        "future_excess_ret_20": -0.058,
        "label": true
      },
      "top_positive_contributions": [],
      "top_negative_contributions": [],
      "factor_group_contributions": []
    },
    "outperform": {
      "score": 0.52,
      "score_pct_rank": 0.9981,
      "score_decile": 10,
      "cohort": "top",
      "observed": {
        "future_ret_20": 0.004,
        "future_excess_ret_20": -0.058,
        "label": false
      },
      "top_positive_contributions": [],
      "top_negative_contributions": [],
      "factor_group_contributions": []
    }
  }
}
```

## Single-Target Response

Use `target=up` or `target=outperform` to return only one target summary.

Important fields:

| Field | Meaning |
| --- | --- |
| `score` | Raw model probability-like score. Do not show it alone as a recommendation. |
| `score_pct_rank` | Same-day cross-sectional percentile rank. Prefer this for UI. |
| `score_decile` | Same-day score decile, 1 low to 10 high. |
| `cohort` | `top`, `upper`, `middle`, `lower`, or `bottom`. |
| `model_role` | `primary` or `fallback`. |
| `warnings` | Model uncertainty and data-quality warnings. Must be displayed. |
| `top_positive_contributions` | Features pushing the score higher. |
| `top_negative_contributions` | Features pushing the score lower. |

## Combined Signal Labels

| Label | Product Meaning |
| --- | --- |
| `strong_positive` | Both absolute upside and relative outperformance scores are high. |
| `absolute_upside_but_weak_relative` | Absolute upside is high, but relative score is weak. |
| `relative_resilience_without_absolute_upside` | Relative score is high, but absolute upside is weak. |
| `weak_negative` | Both target scores are low. |
| `mixed_or_neutral` | No strong aligned signal. |
| `insufficient_data` | One or more target scores are unavailable. |

## Warnings

Warnings are part of the product contract and should not be hidden.

Known warnings include:

| Warning Prefix | Meaning |
| --- | --- |
| `fallback_model_used` | The regime-specific fallback model was used and is experimental. |
| `rolling_validation_window` | The sample is in the 2026 rolling validation window. |
| `outside_validation_windows` | The date is outside configured train/validation/test windows. |
| `neutral_score` | The stock is near the middle of the cross-section. |
| `many_missing_features` | Many model features were imputed. |
| `target_disagreement` | `up` and `outperform` deciles disagree materially. |
| `observed_label_conflict` | Historical labels disagree for this sample. |
| `low_combined_confidence` | Combined signal should not be used standalone. |

## Error Responses

| Status | Condition |
| --- | --- |
| `400` | Missing `ts_code`, missing `trade_date`, invalid target, or invalid input. |
| `404` | No sample rows for the date, or stock not found in that date universe. |
| `503` | Model artifact is missing. |

Example:

```json
{
  "error": "ts_code is required."
}
```

## UI Requirements

- Show both `up` and `outperform` target scores.
- Show `combined_signal.label` and `confidence`.
- Show `warnings` visibly.
- Prefer percentile/decile over raw score.
- Do not present the result as a buy/sell recommendation.
- If `use_fallback=true`, show that the fallback model was used.
