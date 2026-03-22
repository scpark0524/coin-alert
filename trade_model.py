"""
매매 성공 예측 모델 — GradientBoosting (VM 1GB RAM 호환)

사용법:
  python3 trade_model.py train    # 학습 (100건+ 필요)
  python3 trade_model.py stats    # 모델 통계 조회

피처:
  - entry_rsi: 진입 시점 RSI
  - entry_score: 앙상블 점수
  - hold_hours: 보유 시간
  - pnl_pct: 수익률 (학습 시 레이블로도 활용)
  - btc_change_pct: BTC 24h 변동률
  - hour_sin/hour_cos: 매매 시간대 (순환 인코딩)
  - full_percentile: 진입 가격 백분위 (0~100)
  - score: 성공/실패 점수 (-3 ~ +3)

레이블:
  - score > 0 → 성공 (1)
  - score <= 0 → 실패 (0)

Cold Start:
  - 100건 미만 → 학습 불가, 기존 로직만 사용
  - 100건 이상 → 학습 시작
  - Walk-Forward CV: 최근 20% 테스트
"""

import json
import math
import os
import pickle
import sys
from datetime import datetime

import numpy as np

MODEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_model.pkl")
API_URL = "http://localhost:8000/api/v1/projects/coin-alert/trade-analyses?limit=500"
MIN_SAMPLES = 100


def fetch_trade_data():
    """오케스트레이터 API에서 매매 분석 데이터 조회."""
    import requests
    try:
        resp = requests.get(API_URL, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"API 조회 실패: {e}")

    # Fallback: 로컬 trade_history.json
    hist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_history.json")
    if os.path.exists(hist_file):
        with open(hist_file) as f:
            trades = json.load(f)
        # trade_history.json → 간단한 피처 추출
        sells = [t for t in trades if t.get("side") in ("SELL", "PARTIAL_SELL")]
        results = []
        for s in sells:
            results.append({
                "entry_rsi": s.get("entry_rsi", 50),
                "exit_rsi": s.get("exit_rsi", 50),
                "entry_score": s.get("entry_score", 0),
                "hold_hours": s.get("hold_hours", 0),
                "pnl_pct": s.get("pnl_pct", 0),
                "btc_change_pct": s.get("btc_change_pct", 0),
                "trade_timestamp": s.get("timestamp", ""),
                "score": _calc_score(s.get("reason", ""), s.get("pnl_pct", 0)),
            })
        return results
    return []


def _calc_score(reason, pnl_pct):
    """매도 사유별 점수 계산."""
    score_map = {
        "PROFIT_TARGET": 3, "PARTIAL_TP2": 2, "TRAILING_STOP": 2,
        "TP1": 1, "PARTIAL_TP1": 1, "SIGNAL": 1, "RSI_SELL": 1,
        "BREAKEVEN_STOP": 0, "TIME_STOP": -1, "PARTIAL_SL1": -1,
        "STOP_LOSS": -2, "CATASTROPHIC_STOP": -3,
    }
    s = score_map.get(reason, 0)
    if reason in ("SIGNAL", "RSI_SELL") and pnl_pct <= 0:
        s = 0
    return s


def engineer_features(trades):
    """거래 데이터에서 피처 행렬 + 레이블 생성."""
    X = []
    y = []

    for t in trades:
        score = t.get("score", 0)
        ts = t.get("trade_timestamp", "")

        # 시간대 순환 인코딩
        hour = 12  # default
        try:
            if ts:
                hour = int(ts[11:13]) if len(ts) > 13 else 12
        except (ValueError, IndexError):
            pass
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)

        features = [
            t.get("entry_rsi", 50),
            t.get("exit_rsi", 50),
            t.get("entry_score", 0),
            t.get("hold_hours", 0),
            abs(t.get("pnl_pct", 0)),  # 절대값 (방향은 레이블)
            t.get("btc_change_pct", 0),
            hour_sin,
            hour_cos,
        ]

        X.append(features)
        y.append(1 if score > 0 else 0)  # 성공(1) / 실패(0)

    return np.array(X), np.array(y)


FEATURE_NAMES = [
    "entry_rsi", "exit_rsi", "entry_score", "hold_hours",
    "abs_pnl_pct", "btc_change_pct", "hour_sin", "hour_cos",
]


def train():
    """모델 학습 + 저장."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import accuracy_score, classification_report

    print("=" * 60)
    print("  매매 성공 예측 모델 학습")
    print("=" * 60)

    trades = fetch_trade_data()
    sells = [t for t in trades if t.get("side", "SELL") in ("SELL", "PARTIAL_SELL") or "score" in t]

    print(f"\n총 매매 데이터: {len(sells)}건")

    if len(sells) < MIN_SAMPLES:
        print(f"최소 {MIN_SAMPLES}건 필요 (현재 {len(sells)}건)")
        print("   데이터가 축적될 때까지 기존 로직으로 운영합니다.")
        return False

    X, y = engineer_features(sells)

    # Walk-Forward Split: 최근 20% 테스트
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"학습: {len(X_train)}건 | 테스트: {len(X_test)}건")
    print(f"성공 비율: 학습 {y_train.mean():.1%} | 테스트 {y_test.mean():.1%}")

    # GradientBoosting (경량, 1GB RAM 호환)
    model = GradientBoostingClassifier(
        n_estimators=50,      # 적은 트리 수 (과적합 방지 + 메모리 절약)
        max_depth=3,          # 얕은 트리 (일반화)
        learning_rate=0.1,
        min_samples_leaf=5,
        subsample=0.8,
        random_state=42,
    )

    model.fit(X_train, y_train)

    # 평가
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    print(f"\n{'─' * 40}")
    print(f"정확도: {accuracy_score(y_test, y_pred):.1%}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['실패', '성공'])}")

    # 피처 중요도
    importances = model.feature_importances_
    print(f"{'─' * 40}")
    print("피처 중요도:")
    for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: -x[1]):
        bar = "█" * int(imp * 50)
        print(f"  {name:<16} {imp:.3f} {bar}")

    # 저장
    model_data = {
        "model": model,
        "feature_names": FEATURE_NAMES,
        "train_size": len(X_train),
        "test_accuracy": float(accuracy_score(y_test, y_pred)),
        "trained_at": datetime.utcnow().isoformat(),
        "version": "1.0",
    }

    with open(MODEL_FILE, "wb") as f:
        pickle.dump(model_data, f)

    print(f"\n모델 저장: {MODEL_FILE}")
    print(f"   학습 데이터: {len(X_train)}건 | 정확도: {accuracy_score(y_test, y_pred):.1%}")
    return True


def predict(features_dict):
    """단일 거래에 대한 성공 확률 예측.

    Args:
        features_dict: {entry_rsi, exit_rsi, entry_score, hold_hours,
                        abs_pnl_pct, btc_change_pct, hour_sin, hour_cos}

    Returns:
        float: 성공 확률 (0.0 ~ 1.0), 모델 없으면 -1
    """
    if not os.path.exists(MODEL_FILE):
        return -1  # 모델 없음 (cold start)

    try:
        with open(MODEL_FILE, "rb") as f:
            model_data = pickle.load(f)

        model = model_data["model"]
        features = [features_dict.get(name, 0) for name in FEATURE_NAMES]
        prob = model.predict_proba([features])[0][1]
        return float(prob)
    except Exception:
        return -1


def stats():
    """저장된 모델 통계 조회."""
    if not os.path.exists(MODEL_FILE):
        print("학습된 모델 없음 (trade_model.pkl)")
        return

    with open(MODEL_FILE, "rb") as f:
        model_data = pickle.load(f)

    print("=" * 40)
    print("  매매 예측 모델 상태")
    print("=" * 40)
    print(f"  버전: {model_data.get('version', '?')}")
    print(f"  학습일: {model_data.get('trained_at', '?')}")
    print(f"  학습 데이터: {model_data.get('train_size', '?')}건")
    print(f"  테스트 정확도: {model_data.get('test_accuracy', 0):.1%}")

    model = model_data["model"]
    importances = model.feature_importances_
    print(f"\n  피처 중요도:")
    for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: -x[1]):
        print(f"    {name:<16} {imp:.3f}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "train":
        train()
    elif cmd == "stats":
        stats()
    else:
        print(f"Usage: python3 trade_model.py [train|stats]")
