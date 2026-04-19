"""Entry Quality ML Model v2 — Regime-split buy timing prediction.

Trains 3 separate models per regime group:
  - BULLISH  (BULL, MILD_BULL)
  - SIDEWAYS
  - BEARISH  (BEAR, MILD_BEAR)

Each model predicts: GOOD_ENTRY (1) vs BAD_ENTRY (0)
  - GOOD: reached TP1 within 7 days
  - BAD:  didn't reach TP1 or took >7 days

Usage:
  python3 train_entry_model.py          # Train all regime models
  python3 train_entry_model.py --info   # Show data stats only
"""
import json
import os
import sys
import pickle
import warnings
from datetime import datetime
from collections import defaultdict

import numpy as np

warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_FEATURES = os.path.join(SCRIPT_DIR, "ml_features.jsonl")
MODEL_DIR = os.path.join(SCRIPT_DIR, "models")
REPORT_PATH = os.path.join(SCRIPT_DIR, "entry_model_report.json")

# Regime groups
REGIME_GROUPS = {
    "BULLISH": ["BULL", "MILD_BULL"],
    "SIDEWAYS": ["SIDEWAYS"],
    "BEARISH": ["BEAR", "MILD_BEAR"],
}

def _get_regime_group(regime: str) -> str:
    for group, regimes in REGIME_GROUPS.items():
        if regime in regimes:
            return group
    return "SIDEWAYS"

# Entry-time features (available at buy decision)
ENTRY_FEATURES = [
    "entry_rsi",
    "entry_bb_position",
    "entry_adx",
    "entry_score",
    "entry_confidence",
    "entry_volume_ratio",
    "entry_price_percentile",
    "entry_atr_pct",
    "entry_btc_change",
    "entry_hour_kst",
    "entry_day_of_week",
    "entry_is_night",
    "entry_mean_rev_score",
    "entry_momentum_score",
    "entry_trend_score",
    "entry_fear_greed",
    "dca_count",
]

MIN_SAMPLES_PER_REGIME = 20  # Minimum to train a regime-specific model


def load_data():
    """Load JSONL and split by regime group."""
    with open(ML_FEATURES) as f:
        records = [json.loads(l) for l in f.readlines()]

    groups = defaultdict(lambda: {"X": [], "y": [], "meta": []})

    for r in records:
        eq = r.get("entry_quality")
        if eq is None:
            continue
        if r.get("entry_rsi") is None and r.get("entry_score") is None:
            continue

        label = 1 if eq in ("EXCELLENT", "GOOD") else 0
        regime = r.get("entry_regime") or r.get("regime", "SIDEWAYS")
        group = _get_regime_group(regime)

        row = _build_feature_row(r)
        groups[group]["X"].append(row)
        groups[group]["y"].append(label)
        groups[group]["meta"].append({
            "ticker": r.get("ticker"),
            "timestamp": r.get("timestamp"),
            "pnl_pct": r.get("pnl_pct"),
            "holding_hours": r.get("holding_hours"),
            "entry_quality": eq,
            "reason": r.get("reason"),
            "regime": regime,
        })

    result = {}
    for group in groups:
        result[group] = {
            "X": np.array(groups[group]["X"], dtype=np.float64),
            "y": np.array(groups[group]["y"], dtype=np.int32),
            "meta": groups[group]["meta"],
        }
    return result


def _build_feature_row(r: dict) -> list:
    row = []
    for feat in ENTRY_FEATURES:
        if feat == "entry_btc_change":
            row.append(r.get("entry_btc_change") or r.get("btc_change_pct") or 0)
        elif feat == "entry_is_night":
            row.append(1 if r.get("entry_is_night") else 0)
        else:
            val = r.get(feat)
            row.append(val if val is not None else np.nan)
    return row


def train_regime_model(group_name, X, y, meta):
    """Train a model for one regime group."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import classification_report

    n = len(y)
    good_count = int(sum(y))
    bad_count = n - good_count

    print("\n--- %s (%d samples: GOOD %d / BAD %d) ---" % (group_name, n, good_count, bad_count))

    if n < MIN_SAMPLES_PER_REGIME:
        print("  SKIP: not enough data (need %d)" % MIN_SAMPLES_PER_REGIME)
        return None, None

    if good_count == 0 or bad_count == 0:
        print("  SKIP: only one class present")
        return None, None

    # Time-based split 80/20
    split = int(n * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # Handle edge case: test set has only one class
    if len(set(y_test)) < 2:
        print("  WARNING: test set has only one class, using full data for training")
        X_train, y_train = X, y
        X_test, y_test = X[-5:], y[-5:]  # small validation

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf", GradientBoostingClassifier(
            n_estimators=80,
            max_depth=3,
            learning_rate=0.1,
            min_samples_leaf=max(3, n // 20),
            subsample=0.8,
            random_state=42,
        )),
    ])

    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = sum(y_pred == y_test) / len(y_test)
    print("  Accuracy: %.1f%% (train: %d, test: %d)" % (accuracy * 100, len(y_train), len(y_test)))

    # Feature importance
    importances = model.named_steps["clf"].feature_importances_
    feat_imp = sorted(zip(ENTRY_FEATURES, importances), key=lambda x: -x[1])
    print("  Top features:")
    for feat, imp in feat_imp[:5]:
        print("    %-25s %.3f" % (feat, imp))

    report = {
        "group": group_name,
        "samples": n,
        "good_ratio": round(good_count / n, 3),
        "accuracy": round(accuracy, 4),
        "feature_importance": {f: round(i, 4) for f, i in feat_imp},
    }

    return model, report


def train_all():
    """Train regime-split models and save."""
    os.makedirs(MODEL_DIR, exist_ok=True)

    data = load_data()

    print("=" * 50)
    print("Entry Quality ML — Regime-Split Training")
    print("=" * 50)

    total = sum(len(d["y"]) for d in data.values())
    print("Total valid samples: %d" % total)
    for group in ["BULLISH", "SIDEWAYS", "BEARISH"]:
        if group in data:
            n = len(data[group]["y"])
            good = int(sum(data[group]["y"]))
            print("  %s: %d (GOOD: %d, BAD: %d)" % (group, n, good, n - good))

    models = {}
    reports = {}
    fallback_X, fallback_y = [], []

    for group in ["BULLISH", "SIDEWAYS", "BEARISH"]:
        if group not in data:
            print("\n--- %s (0 samples) --- SKIP" % group)
            continue

        d = data[group]
        model, report = train_regime_model(group, d["X"], d["y"], d["meta"])

        if model is not None:
            model_path = os.path.join(MODEL_DIR, "entry_%s.pkl" % group.lower())
            with open(model_path, "wb") as f:
                pickle.dump(model, f)
            models[group] = model
            reports[group] = report
            print("  Saved: %s" % model_path)

        # Accumulate for fallback model
        fallback_X.extend(d["X"])
        fallback_y.extend(d["y"])

    # Train fallback (all-regime) model
    print("\n--- FALLBACK (all regimes combined) ---")
    fb_X = np.array(fallback_X, dtype=np.float64)
    fb_y = np.array(fallback_y, dtype=np.int32)
    fb_model, fb_report = train_regime_model("FALLBACK", fb_X, fb_y, [])
    if fb_model is not None:
        fb_path = os.path.join(MODEL_DIR, "entry_fallback.pkl")
        with open(fb_path, "wb") as f:
            pickle.dump(fb_model, f)
        reports["FALLBACK"] = fb_report
        print("  Saved: %s" % fb_path)

    # Save combined report
    full_report = {
        "trained_at": datetime.utcnow().isoformat(),
        "total_samples": total,
        "regime_reports": reports,
        "features_used": ENTRY_FEATURES,
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False)
    print("\nReport saved: %s" % REPORT_PATH)


def load_model(regime: str):
    """Load the appropriate model for a regime. Falls back to combined model."""
    group = _get_regime_group(regime)
    model_path = os.path.join(MODEL_DIR, "entry_%s.pkl" % group.lower())

    if os.path.exists(model_path):
        with open(model_path, "rb") as f:
            return pickle.load(f), group

    # Fallback
    fb_path = os.path.join(MODEL_DIR, "entry_fallback.pkl")
    if os.path.exists(fb_path):
        with open(fb_path, "rb") as f:
            return pickle.load(f), "FALLBACK"

    return None, None


def predict_entry(entry_context: dict) -> dict:
    """Predict entry quality for a new buy signal.

    Called from coin_alert.py at buy decision time.
    Returns: {"score": 0.0-1.0, "label": "GOOD"/"BAD",
              "recommendation": "STRONG_BUY"/"BUY"/"WEAK_BUY"/"SKIP",
              "regime_group": str}
    """
    regime = entry_context.get("entry_regime") or entry_context.get("market_regime", "SIDEWAYS")
    model, group = load_model(regime)

    if model is None:
        return {"score": 0.5, "label": "UNKNOWN", "recommendation": "NO_MODEL", "regime_group": "NONE"}

    row = _build_feature_row(entry_context)
    X = np.array([row], dtype=np.float64)
    prob = model.predict_proba(X)[0][1]
    label = "GOOD" if prob >= 0.5 else "BAD"

    if prob >= 0.7:
        rec = "STRONG_BUY"
    elif prob >= 0.5:
        rec = "BUY"
    elif prob >= 0.3:
        rec = "WEAK_BUY"
    else:
        rec = "SKIP"

    return {
        "score": round(prob, 3),
        "label": label,
        "recommendation": rec,
        "regime_group": group,
    }


def main():
    if "--info" in sys.argv:
        data = load_data()
        total = sum(len(d["y"]) for d in data.values())
        print("Samples: %d" % total)
        for g, d in sorted(data.items()):
            print("  %s: %d (GOOD: %d)" % (g, len(d["y"]), int(sum(d["y"]))))
        return

    if not os.path.exists(ML_FEATURES):
        print("ERROR: %s not found. Run backfill_jsonl.py first." % ML_FEATURES)
        sys.exit(1)

    train_all()


if __name__ == "__main__":
    main()
