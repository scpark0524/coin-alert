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
MIN_SAMPLES = 30   # 실시간 webhook 데이터(RSI/점수 포함) 30건부터 학습 가능


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


def _calc_score(reason, pnl_pct, hold_hours=0):
    """PnL 기반 연속 점수 + 시간 효율 보정 + 노이즈 SL 감점."""
    score = pnl_pct
    if hold_hours > 48:
        score -= min(2.0, (hold_hours - 48) / 48)
    if reason in ("STOP_LOSS", "PARTIAL_SL1", "CATASTROPHIC_STOP") and hold_hours < 4:
        score -= 1.5
    if pnl_pct < -5:
        score = pnl_pct * 1.5 - (1.5 if hold_hours < 4 else 0)
    if pnl_pct >= 10:
        score += 1.0
    return round(score, 2)


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
        y.append(score)  # 연속 점수 (regression target)

    return np.array(X), np.array(y)


FEATURE_NAMES = [
    "entry_rsi", "exit_rsi", "entry_score", "hold_hours",
    "abs_pnl_pct", "btc_change_pct", "hour_sin", "hour_cos",
]


def train():
    """모델 학습 + 저장. Regression으로 연속 점수 예측."""
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error, r2_score

    print("=" * 60)
    print("  매매 점수 예측 모델 학습 (Regression)")
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
    print(f"점수 분포: 학습 평균 {y_train.mean():+.2f} | 테스트 평균 {y_test.mean():+.2f}")

    # GradientBoosting Regressor (연속 점수 예측)
    model = GradientBoostingRegressor(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        min_samples_leaf=5,
        subsample=0.8,
        random_state=42,
    )

    model.fit(X_train, y_train)

    # 평가
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # 방향 정확도 (예측 부호 == 실제 부호)
    direction_acc = np.mean((y_pred > 0) == (y_test > 0))

    print(f"\n{'─' * 40}")
    print(f"MAE (평균 절대 오차): {mae:.2f}")
    print(f"R2 Score: {r2:.3f}")
    print(f"방향 정확도 (수익/손실 맞춤): {direction_acc:.1%}")

    # 임계값별 정밀도
    for threshold in [0.0, 0.5, 1.0]:
        pred_buy = y_pred > threshold
        if pred_buy.sum() > 0:
            actual_success = y_test[pred_buy].mean()
            print(f"  예측점수 > {threshold}: {pred_buy.sum()}건 중 실제 평균 {actual_success:+.2f}")

    # 피처 중요도
    importances = model.feature_importances_
    print(f"\n{'─' * 40}")
    print("피처 중요도:")
    for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: -x[1]):
        bar = "█" * int(imp * 50)
        print(f"  {name:<16} {imp:.3f} {bar}")

    # 저장
    model_data = {
        "model": model,
        "feature_names": FEATURE_NAMES,
        "train_size": len(X_train),
        "test_mae": float(mae),
        "test_r2": float(r2),
        "test_direction_acc": float(direction_acc),
        "trained_at": datetime.utcnow().isoformat(),
        "version": "2.0",
        "type": "regressor",
    }

    with open(MODEL_FILE, "wb") as f:
        pickle.dump(model_data, f)

    print(f"\n모델 저장: {MODEL_FILE}")
    print(f"   학습: {len(X_train)}건 | MAE: {mae:.2f} | 방향정확도: {direction_acc:.1%}")
    return True


def predict(features_dict):
    """단일 거래에 대한 예측 점수 반환.

    Args:
        features_dict: {entry_rsi, exit_rsi, entry_score, hold_hours,
                        abs_pnl_pct, btc_change_pct, hour_sin, hour_cos}

    Returns:
        float: 예측 점수 (양수=성공 예상, 음수=실패 예상), 모델 없으면 None
    """
    if not os.path.exists(MODEL_FILE):
        return None

    try:
        with open(MODEL_FILE, "rb") as f:
            model_data = pickle.load(f)

        model = model_data["model"]
        features = [features_dict.get(name, 0) for name in FEATURE_NAMES]
        score = model.predict([features])[0]
        return round(float(score), 2)
    except Exception:
        return None


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
    print(f"  버전: {model_data.get('version', '?')} ({model_data.get('type', 'classifier')})")
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
