"""ML 보조필터 백테스트 — quality_score >= 0.5 이진분류"""
import json
import numpy as np
import warnings
warnings.filterwarnings("ignore")

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, confusion_matrix)

# 데이터 로드
lines = open("data/ml_features.jsonl").readlines()
data = [json.loads(l) for l in lines]
labeled = sorted(
    [d for d in data if d.get("quality_score") is not None],
    key=lambda x: x["timestamp"]
)

FEATURES = [
    "entry_rsi", "entry_adx", "entry_bb_position", "entry_confidence",
    "entry_score", "entry_volume_ratio", "entry_price_percentile",
    "entry_atr_pct", "btc_change_pct", "entry_btc_change",
    "entry_fear_greed", "dca_count", "tp_level", "regime_tp1_pct",
    "entry_hour_kst", "entry_is_weekend",
]
REGIMES = ["BEAR", "MILD_BEAR", "SIDEWAYS", "MILD_BULL", "BULL", "VOLATILE"]
feat_names = FEATURES + [f"regime_{r}" for r in REGIMES]


def extract(d):
    row = []
    for f in FEATURES:
        v = d.get(f)
        row.append(float(v) if v is not None else np.nan)
    reg = d.get("entry_regime", "")
    for r in REGIMES:
        row.append(1.0 if reg == r else 0.0)
    return row


X = np.array([extract(d) for d in labeled])
y = np.array([1 if d["quality_score"] >= 0.5 else 0 for d in labeled])
ts = [d["timestamp"][:10] for d in labeled]

# NaN → 중앙값
med = np.nanmedian(X, axis=0)
for j in range(X.shape[1]):
    m = np.isnan(X[:, j])
    X[m, j] = med[j]

# 시간순 분할: train ~5월 / test 6~7월
split = "2026-06-01"
tri = [i for i, t in enumerate(ts) if t < split]
tei = [i for i, t in enumerate(ts) if t >= split]
Xtr, ytr = X[tri], y[tri]
Xte, yte = X[tei], y[tei]
test_data = [labeled[i] for i in tei]
base_pnl = sum(d["pnl_pct"] for d in test_data)

print(f"총 라벨: {len(labeled)}건 | Train: {len(tri)}건 (성공률 {sum(ytr)/len(ytr)*100:.0f}%) | Test: {len(tei)}건 (성공률 {sum(yte)/len(yte)*100:.0f}%)")
print(f"기준선: {len(test_data)}건, 총PnL: {base_pnl:+.1f}%, 평균PnL: {base_pnl/len(test_data):+.2f}%")

sc = StandardScaler()
Xtrs = sc.fit_transform(Xtr)
Xtes = sc.transform(Xte)

models = {
    "Logistic Regression": (
        LogisticRegression(max_iter=1000, C=0.1, class_weight="balanced", random_state=42),
        True,  # needs scaling
    ),
    "Gradient Boosting": (
        GradientBoostingClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.05,
            min_samples_leaf=10, subsample=0.8, random_state=42
        ),
        False,
    ),
    "Random Forest": (
        RandomForestClassifier(
            n_estimators=200, max_depth=5, min_samples_leaf=10,
            class_weight="balanced", random_state=42
        ),
        False,
    ),
}

for name, (mdl, use_scale) in models.items():
    if use_scale:
        mdl.fit(Xtrs, ytr)
        proba = mdl.predict_proba(Xtes)[:, 1]
    else:
        mdl.fit(Xtr, ytr)
        proba = mdl.predict_proba(Xte)[:, 1]

    pred = (proba >= 0.5).astype(int)
    cm = confusion_matrix(yte, pred)

    print(f"\n{'='*65}")
    print(f"  {name}")
    print(f"{'='*65}")
    print(f"  Accuracy:  {accuracy_score(yte, pred):.3f}")
    print(f"  Precision: {precision_score(yte, pred, zero_division=0):.3f}")
    print(f"  Recall:    {recall_score(yte, pred):.3f}")
    print(f"  F1:        {f1_score(yte, pred):.3f}")
    print(f"  AUC-ROC:   {roc_auc_score(yte, proba):.3f}")
    print(f"  Confusion: TN={cm[0][0]}  FP={cm[0][1]}  FN={cm[1][0]}  TP={cm[1][1]}")

    # 피처 중요도
    if hasattr(mdl, "feature_importances_"):
        fi = mdl.feature_importances_
        top = np.argsort(fi)[::-1][:8]
        print(f"\n  Top 8 피처 (importance):")
        for i in top:
            print(f"    {feat_names[i]:35s} {fi[i]:.3f}")
    elif hasattr(mdl, "coef_"):
        c = mdl.coef_[0]
        top = np.argsort(np.abs(c))[::-1][:8]
        print(f"\n  Top 8 피처 (계수):")
        for i in top:
            print(f"    {feat_names[i]:35s} {c[i]:+.3f}")

    # 스코어 구간별 실제 성공률
    print(f"\n  스코어 구간별:")
    for lo, hi in [(0, 0.3), (0.3, 0.45), (0.45, 0.55), (0.55, 0.7), (0.7, 1.01)]:
        mask = [(lo <= p < hi) for p in proba]
        if sum(mask) == 0:
            continue
        act = [yte[i] for i, m in enumerate(mask) if m]
        pnls = [test_data[i]["pnl_pct"] for i, m in enumerate(mask) if m]
        sr = sum(act) / len(act) * 100
        ap = sum(pnls) / len(pnls)
        print(f"    [{lo:.2f}-{hi:.2f}) {sum(mask):>3d}건 | 성공률: {sr:>5.1f}% | 평균PnL: {ap:+.2f}%")

    # 사이징 시뮬레이션
    print(f"\n  포지션 사이징 시뮬:")
    for sname, rules in [
        ("보수적 (low=스킵)", [(0.6, 1.0), (0.35, 0.5), (0, 0.0)]),
        ("중립 (low=축소)", [(0.6, 1.0), (0.35, 0.5), (0, 0.2)]),
    ]:
        wp = tw = tc = 0
        for d, p in zip(test_data, proba):
            w = 0
            for th, mu in rules:
                if p >= th:
                    w = mu
                    break
            if w == 0:
                continue
            wp += d["pnl_pct"] * w
            tw += w
            tc += 1
        wa = wp / tw if tw > 0 else 0
        print(f"    [{sname}]")
        print(f"      거래: {tc}/{len(test_data)}건 | 가중PnL: {wp:+.1f}% (기준: {base_pnl:+.1f}%) | 평균: {wa:+.2f}% (기준: {base_pnl/len(test_data):+.2f}%)")
