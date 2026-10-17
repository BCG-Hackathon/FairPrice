"""Verify the team's saved model without overwriting their model or metrics.

Run: .venv/Scripts/python ml/verify_saved.py
Only load model.pkl from this reviewed team repository, not untrusted uploads.
"""
import hashlib
import json
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
import joblib
import numpy as np
from features import add_features, build_panel, load_processed, to_model_frame, training_rows
from train import holdout_split, fit_model, evaluate, build_snapshot
import config


def main():
    data = load_processed()
    artifact = joblib.load(config.MODEL_FILE)
    feat = add_features(build_panel(data))
    rows = training_rows(feat)
    train, test, cutoff = holdout_split(rows)
    model = fit_model(to_model_frame(train, artifact["categories"]), train["target"])
    test = test.copy()
    test["pred_price"] = test["price"] * np.exp(model.predict(to_model_frame(test, artifact["categories"]), num_threads=2))
    test["naive_price"] = test["price"]
    metrics = evaluate(test)
    saved = json.loads(config.METRICS_FILE.read_text())
    # Validate both held-out score reproduction and deployed final-model forecasts.
    latest = build_snapshot(feat, artifact["model"], artifact["categories"], artifact["use_model_for"], data["month"].max())
    snap = json.loads(config.SNAPSHOT_JSON.read_text())["rows"]
    expected = {(r["crop"], r["market"], r["observed_price_type"]): r["observed_forecast"] for r in snap}
    forecast_match = all(expected[(r.crop, r.market, r.pricetype)] == r.forecast_price for r in latest.itertuples())
    report = {
        "processed_sha256": hashlib.sha256(config.PROCESSED_FILE.read_bytes()).hexdigest(),
        "model_sha256": hashlib.sha256(config.MODEL_FILE.read_bytes()).hexdigest(),
        "observations": len(data), "labelled_pairs": len(rows), "train_pairs": len(train),
        "test_pairs": len(test), "test_origin_from": str(cutoff.date()),
        "model_metadata": {k: artifact[k] for k in ("trained_at", "data_end", "target", "use_model_for")},
        "holdout_overall_matches_saved": metrics["overall"] == saved["overall"],
        "holdout_by_crop_matches_saved": metrics["by_crop"] == saved["by_crop"],
        "saved_model_forecasts_match_snapshot": forecast_match,
        "reproduced_metrics": metrics,
        "limitation": "Reproduces processed-data results only; original raw CSV and centred outlier filtering remain unaudited."
    }
    destination = config.REPO_DIR / "docs" / "model-verification.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
