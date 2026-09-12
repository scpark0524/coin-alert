"""Entry Quality ML Model v3 — Observe-only quality_score predictor.

Logistic Regression 계수를 임베딩하여 sklearn 없이 예측.
타겟: quality_score >= 0.5 (성공 거래 이진분류)
용도: 관찰 모드 — 스코어 기록만, 매매 차단/사이징 변경 없음.

Usage:
  python3 train_entry_model.py          # 전체 데이터로 재학습 (sklearn 필요)
  python3 train_entry_model.py --info   # 데이터 통계만 출력
"""
import json
import math
import os
import sys
from datetime import datetime

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_FEATURES = os.path.join(SCRIPT_DIR, "ml_features.jsonl")
MODEL_JSON = os.path.join(SCRIPT_DIR, "data", "lr_quality_model.json")

# ─── 피처 정의 ───
FEATURES = [
    "entry_rsi", "entry_adx", "entry_bb_position", "entry_confidence",
    "entry_score", "entry_volume_ratio", "entry_price_percentile",
    "entry_atr_pct", "btc_change_pct", "entry_btc_change",
    "entry_fear_greed", "dca_count", "tp_level", "regime_tp1_pct",
    "entry_hour_kst", "entry_is_weekend",
]
REGIMES = ["BEAR", "MILD_BEAR", "SIDEWAYS", "MILD_BULL", "BULL", "VOLATILE"]
ALL_FEATURES = FEATURES + ["regime_" + r for r in REGIMES]

# ─── 임베딩 계수 (2026-07-18 학습, 433건) ───
_LR_INTERCEPT = 0.057161
_LR_COEF = [
    0.332263, 0.054883, -0.119488, -0.055939, 0.207511, -0.046272,
    -0.433078, 0.111050, -0.323013, -0.136447, -0.255220, -0.574095,
    0.243187, 0.907812, -0.148374, 0.009962, 0.000352, -0.461165,
    0.132601, 0.105073, 0.049038, 0.0,
]
_LR_MEAN = [
    20.373441, 35.532564, -0.039219, 78.593533, 35.757737, 0.948314,
    6.380947, 1.505912, 0.333303, 0.542263, 22.341801, 0.300231,
    0.545035, 3.112009, 12.436490, 0.184758, 0.048499, 0.085450,
    0.251732, 0.316397, 0.297921, 0.0,
]
_LR_SCALE = [
    9.045436, 17.284222, 0.190777, 16.055796, 14.597388, 1.620660,
    5.623661, 0.735925, 1.472316, 1.407832, 12.606810, 0.681274,
    0.591260, 0.598917, 6.240837, 0.388101, 0.214818, 0.279551,
    0.434008, 0.465070, 0.457345, 1.0,
]
_LR_MEDIANS = [
    22.2, 31.9, -0.041, 80.0, 37.6, 0.46, 4.95, 1.34, 0.34, 0.55,
    20.0, 0.0, 0.0, 3.0, 12.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
]


def _sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ez = math.exp(x)
    return ez / (1.0 + ez)


def _extract_features(ctx: dict) -> list:
    """entry_context에서 피처 벡터 추출."""
    row = []
    for f in FEATURES:
        if f == "entry_btc_change":
            v = ctx.get("entry_btc_change") or ctx.get("btc_change_pct")
        elif f == "btc_change_pct":
            v = ctx.get("btc_change_pct") or ctx.get("entry_btc_change")
        elif f == "entry_bb_position":
            v = ctx.get("entry_bb_position") or ctx.get("bb_position")
        else:
            v = ctx.get(f)
        row.append(float(v) if v is not None else None)
    # regime 원핫
    regime = ctx.get("entry_regime", "")
    for r in REGIMES:
        row.append(1.0 if regime == r else 0.0)
    return row


def predict_entry(entry_context: dict) -> dict:
    """매수 시점 품질 예측 — 순수 Python, sklearn 불필요.

    Returns: {"score": 0.0-1.0, "label": "GOOD"/"BAD",
              "recommendation": "STRONG_BUY"/"BUY"/"WEAK_BUY"/"SKIP",
              "regime_group": str}
    """
    regime = entry_context.get("entry_regime", "SIDEWAYS")
    if regime in ("BULL", "MILD_BULL"):
        rg = "BULLISH"
    elif regime in ("BEAR", "MILD_BEAR"):
        rg = "BEARISH"
    else:
        rg = "SIDEWAYS"

    row = _extract_features(entry_context)

    # NaN → 중앙값 대체, StandardScaler 적용
    z = 0.0
    for i in range(len(row)):
        val = row[i] if row[i] is not None else _LR_MEDIANS[i]
        scaled = (val - _LR_MEAN[i]) / _LR_SCALE[i] if _LR_SCALE[i] != 0 else 0.0
        z += _LR_COEF[i] * scaled
    z += _LR_INTERCEPT

    prob = _sigmoid(z)
    prob = round(prob, 3)

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
        "score": prob,
        "label": label,
        "recommendation": rec,
        "regime_group": rg,
    }


def train_and_export():
    """전체 데이터로 LR 재학습 후 계수 출력 (sklearn 필요)."""
    import warnings
    warnings.filterwarnings("ignore")
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_auc_score

    with open(ML_FEATURES) as f:
        records = [json.loads(l) for l in f.readlines()]

    labeled = sorted(
        [r for r in records if r.get("quality_score") is not None],
        key=lambda x: x["timestamp"],
    )
    print("총 라벨 유효: %d건" % len(labeled))

    X = np.array([_extract_features(r) for r in labeled], dtype=np.float64)
    y = np.array([1 if r["quality_score"] >= 0.5 else 0 for r in labeled])

    # NaN → 중앙값
    medians = np.nanmedian(X, axis=0)
    for j in range(X.shape[1]):
        m = np.isnan(X[:, j])
        X[m, j] = medians[j]

    sc = StandardScaler()
    Xs = sc.fit_transform(X)
    lr = LogisticRegression(max_iter=1000, C=0.1, class_weight="balanced", random_state=42)
    lr.fit(Xs, y)

    # 시간순 검증 (마지막 20%)
    split = int(len(labeled) * 0.8)
    Xs_test = sc.transform(X[split:])
    y_test = y[split:]
    proba_test = lr.predict_proba(Xs_test)[:, 1]
    auc = roc_auc_score(y_test, proba_test) if len(set(y_test)) > 1 else 0.0

    print("성공률: %.1f%% (성공 %d / 실패 %d)" % (
        sum(y) / len(y) * 100, sum(y), len(y) - sum(y)))
    print("Test AUC: %.3f (마지막 %d건)" % (auc, len(y_test)))

    # 계수 출력
    export = {
        "model_type": "logistic_regression",
        "target": "quality_score >= 0.5",
        "trained_at": datetime.utcnow().isoformat(),
        "train_samples": len(labeled),
        "train_success_rate": round(float(sum(y)) / len(y), 3),
        "test_auc": round(auc, 3),
        "features": ALL_FEATURES,
        "intercept": round(float(lr.intercept_[0]), 6),
        "coef": [round(float(c), 6) for c in lr.coef_[0]],
        "scaler_mean": [round(float(m), 6) for m in sc.mean_],
        "scaler_scale": [round(float(s), 6) for s in sc.scale_],
        "medians": [round(float(m), 6) for m in medians],
    }

    os.makedirs(os.path.dirname(MODEL_JSON), exist_ok=True)
    with open(MODEL_JSON, "w") as f:
        json.dump(export, f, indent=2, ensure_ascii=False)
    print("모델 저장: %s" % MODEL_JSON)

    # Python 코드로 출력 (임베딩용)
    print("\n# ─── train_entry_model.py에 임베딩할 계수 ───")
    print("_LR_INTERCEPT = %.6f" % lr.intercept_[0])
    print("_LR_COEF = %s" % [round(float(c), 6) for c in lr.coef_[0]])
    print("_LR_MEAN = %s" % [round(float(m), 6) for m in sc.mean_])
    print("_LR_SCALE = %s" % [round(float(s), 6) for s in sc.scale_])
    print("_LR_MEDIANS = %s" % [round(float(m), 6) for m in medians])

    # Top 피처
    coef_abs = np.abs(lr.coef_[0])
    top = np.argsort(coef_abs)[::-1][:10]
    print("\nTop 10 피처:")
    for i in top:
        print("  %-35s %+.3f" % (ALL_FEATURES[i], lr.coef_[0][i]))


def main():
    if "--info" in sys.argv:
        with open(ML_FEATURES) as f:
            records = [json.loads(l) for l in f.readlines()]
        labeled = [r for r in records if r.get("quality_score") is not None]
        print("총 레코드: %d, 라벨 유효: %d" % (len(records), len(labeled)))
        if labeled:
            succ = sum(1 for r in labeled if r["quality_score"] >= 0.5)
            print("성공: %d (%.1f%%), 실패: %d" % (succ, succ / len(labeled) * 100, len(labeled) - succ))
        return

    if not os.path.exists(ML_FEATURES):
        print("ERROR: %s not found" % ML_FEATURES)
        sys.exit(1)

    train_and_export()


if __name__ == "__main__":
    main()
