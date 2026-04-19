"""JSONL Backfill — trade_history.json -> ml_features.jsonl 소급 생성.

기존 ml_features.jsonl의 null 껍데기를 제거하고,
trade_history의 매도 기록 + BUY entry_context를 매칭하여
ML 학습용 피처를 재생성한다.

사용법: python3 backfill_jsonl.py
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRADE_HISTORY = os.path.join(SCRIPT_DIR, "trade_history.json")
ML_FEATURES = os.path.join(SCRIPT_DIR, "ml_features.jsonl")
ML_FEATURES_BACKUP = os.path.join(SCRIPT_DIR, "ml_features.jsonl.bak")

# coin_alert.py constants (duplicated to avoid import side effects)
STUCK_HOURS_THRESHOLD = 168  # 7 days
PROFIT_TARGET_2ND = 8.0
LOSS_CUT_PCT = 30.0
DCA_MAX_ADDS = 2
STUCK_PENALTY_PER_DAY = 0.01
MAX_STUCK_PENALTY = 0.2

REGIME_TP1 = {
    "BULL": 4.0, "MILD_BULL": 3.5, "SIDEWAYS": 3.0,
    "MILD_BEAR": 2.5, "BEAR": 2.0,
}


def classify_trade(pnl_pct, holding_hours):
    if pnl_pct is None or holding_hours is None:
        return None
    if pnl_pct >= 2.0:
        return "WIN"
    if pnl_pct < -5.0 or (holding_hours > STUCK_HOURS_THRESHOLD and pnl_pct < 0):
        return "STUCK_LOSS"
    return "NEUTRAL"


def compute_quality_score(pnl_pct, holding_hours, max_pnl, regime):
    """Simplified quality score matching coin_alert.py logic."""
    if pnl_pct is None or holding_hours is None:
        return None
    w = {"pnl": 0.4, "time_efficiency": 0.1, "risk_adjusted": 0.3, "regime_fit": 0.2}
    pnl_score = max(-1.0, min(1.0, pnl_pct / 10.0))
    import math
    time_score = max(0, 1.0 - math.log2(max(holding_hours, 1)) / 10)
    _mfe = max_pnl if max_pnl and max_pnl > 0 else max(pnl_pct, 0.01)
    risk_score = max(-1.0, min(1.0, pnl_pct / max(abs(_mfe), 0.01)))
    regime_fit = 1.0 if regime in ("BULL", "MILD_BULL") else (0.5 if regime == "SIDEWAYS" else 0.0)
    path_penalty = 0.0
    if max_pnl and max_pnl > 0 and pnl_pct is not None:
        giveback = max_pnl - pnl_pct
        if giveback > 5:
            path_penalty = min(0.3, giveback / 100)
    stuck_penalty = 0.0
    if holding_hours > STUCK_HOURS_THRESHOLD:
        excess_days = (holding_hours - STUCK_HOURS_THRESHOLD) / 24
        stuck_penalty = min(MAX_STUCK_PENALTY, excess_days * STUCK_PENALTY_PER_DAY)
    total = (w["pnl"] * pnl_score + w["time_efficiency"] * time_score +
             w["risk_adjusted"] * risk_score + w["regime_fit"] * regime_fit -
             path_penalty - stuck_penalty)
    return round(total, 4)


def build_features_from_trade(sell_record, entry_context, regime="SIDEWAYS"):
    """Build ML feature dict from a trade_history sell record + matched entry_context."""
    pnl_pct = sell_record.get("pnl_pct", 0)
    entry_price = sell_record.get("entry_price", 0)
    exit_price = sell_record.get("price", 0)
    reason = sell_record.get("reason", "")
    ticker = sell_record.get("ticker", "")
    action = sell_record.get("side", "SELL")
    timestamp = sell_record.get("timestamp", "")

    # Holding hours from entry_context match
    holding_hours = None
    if entry_context and entry_context.get("_buy_timestamp"):
        try:
            buy_dt = datetime.fromisoformat(entry_context["_buy_timestamp"].replace("Z", "+00:00"))
            sell_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            holding_hours = round((sell_dt - buy_dt).total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            pass

    ec = entry_context or {}
    entry_regime = ec.get("entry_regime") or ec.get("market_regime") or regime
    regime_tp1 = REGIME_TP1.get(entry_regime, 3.0)
    max_pnl = ec.get("high_pnl", max(pnl_pct, 0) if pnl_pct else 0)
    btc_chg = ec.get("btc_change_pct")

    features = {
        "timestamp": timestamp,
        "ticker": ticker,
        "action": action,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
        "holding_hours": holding_hours,
        "regime": entry_regime,
        "entry_score": ec.get("entry_score"),
        "reason": reason,
    }

    # Alpha PnL
    features["btc_change_pct"] = btc_chg
    features["alpha_pnl"] = round(pnl_pct - btc_chg, 4) if isinstance(btc_chg, (int, float)) else pnl_pct

    # Classification labels
    features["trade_class"] = classify_trade(pnl_pct, holding_hours)

    # Entry quality label (NEW - for buy timing ML)
    if holding_hours is not None and pnl_pct is not None:
        if pnl_pct >= regime_tp1 and holding_hours <= 48:
            features["entry_quality"] = "EXCELLENT"  # TP1 within 48h
        elif pnl_pct >= regime_tp1 and holding_hours <= 168:
            features["entry_quality"] = "GOOD"  # TP1 within 7 days
        elif pnl_pct >= 0 and holding_hours <= 168:
            features["entry_quality"] = "FAIR"  # positive but no TP1 yet
        else:
            features["entry_quality"] = "POOR"  # stuck or loss
    else:
        features["entry_quality"] = None

    # Stuck features
    is_stuck = 1 if (holding_hours and holding_hours > STUCK_HOURS_THRESHOLD and (pnl_pct or 0) < 0) else 0
    features["is_stuck"] = is_stuck
    features["stuck_age_days"] = round(max(0, (holding_hours or 0) - STUCK_HOURS_THRESHOLD) / 24, 2) if is_stuck else 0.0
    features["loss_band"] = 0 if (pnl_pct or 0) >= 0 else (1 if pnl_pct >= -2 else (2 if pnl_pct >= -5 else (3 if pnl_pct >= -10 else 4)))

    # TP features
    features["tp1_reached"] = 1 if (max_pnl is not None and max_pnl >= regime_tp1) else 0
    features["regime_tp1_pct"] = regime_tp1
    features["tp2_reached"] = 1 if (max_pnl is not None and max_pnl >= PROFIT_TARGET_2ND) else 0
    features["distance_to_tp2_pct"] = round(PROFIT_TARGET_2ND - (pnl_pct or 0), 2)

    # MFE/MAE
    _mfe = max_pnl if max_pnl and max_pnl > 0 else 0
    features["mfe_capture_ratio"] = round(max(-2.0, min(1.0, pnl_pct / _mfe)), 4) if _mfe > 0 else (1.0 if pnl_pct >= 0 else 0.0)
    features["mfe_to_tp1_ratio"] = round((max_pnl or 0) / max(regime_tp1, 0.1), 2)
    _low_pnl = ec.get("min_pnl_during_hold", 0)
    features["min_pnl_during_hold"] = _low_pnl
    features["mae_recovery_pp"] = round(max(-50.0, min(50.0, (pnl_pct or 0) - _low_pnl)), 2)

    # Stuck penalty
    _stuck_pen = 0.0
    if holding_hours and holding_hours > STUCK_HOURS_THRESHOLD:
        _stuck_pen = min(MAX_STUCK_PENALTY, ((holding_hours - STUCK_HOURS_THRESHOLD) / 24) * STUCK_PENALTY_PER_DAY)
    features["stuck_penalty"] = round(_stuck_pen, 4)

    # Entry-time features (THE KEY FEATURES for buy timing ML)
    features["entry_rsi"] = ec.get("entry_rsi")
    features["entry_bb_position"] = ec.get("bb_position")
    features["entry_adx"] = ec.get("entry_adx")
    features["entry_confidence"] = ec.get("entry_confidence")
    features["entry_volume_ratio"] = ec.get("entry_volume_ratio") or ec.get("volume_ratio")
    features["entry_price_percentile"] = ec.get("entry_price_percentile") or ec.get("price_percentile")
    features["entry_btc_change"] = ec.get("btc_change_pct")
    features["entry_atr_pct"] = ec.get("entry_atr_pct")
    features["entry_score"] = ec.get("entry_score")
    features["entry_regime"] = ec.get("entry_regime") or ec.get("market_regime")
    features["entry_fear_greed"] = ec.get("fear_greed")

    # Entry timing features (NEW - for buy timing ML)
    features["entry_hour_kst"] = ec.get("entry_hour_kst")
    features["entry_day_of_week"] = ec.get("entry_day_of_week")
    features["entry_is_night"] = ec.get("entry_is_night")

    # Sub-strategy scores (NEW - which strategy drove the buy)
    features["entry_mean_rev_score"] = ec.get("entry_mean_rev_score")
    features["entry_momentum_score"] = ec.get("entry_momentum_score")
    features["entry_trend_score"] = ec.get("entry_trend_score")

    # DCA info
    features["dca_count"] = ec.get("dca_count", 0)
    features["tp_level"] = ec.get("tp_level", 0)

    # Derived features
    features["position_age_days"] = round((holding_hours or 0) / 24, 2)
    features["pnl_per_day"] = round(pnl_pct / max((holding_hours or 0) / 24, 0.04), 4) if pnl_pct is not None else None

    # Quality score
    features["quality_score"] = compute_quality_score(pnl_pct, holding_hours, max_pnl, entry_regime)

    # Exit timing
    try:
        sell_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        exit_kst = sell_dt.astimezone(KST)
        features["is_weekend"] = 1 if exit_kst.weekday() >= 5 else 0
        features["exit_day_of_week"] = exit_kst.weekday()
        features["exit_hour_kst"] = exit_kst.hour
    except (ValueError, TypeError):
        features["is_weekend"] = None
        features["exit_day_of_week"] = None
        features["exit_hour_kst"] = None

    return features


def main():
    # Load trade history
    with open(TRADE_HISTORY) as f:
        trades = json.load(f)

    # Build BUY entry_context map: ticker -> [(timestamp, entry_context, buy_record)]
    buy_map = defaultdict(list)
    for t in trades:
        if t.get("side", "").upper() == "BUY":
            ec = t.get("entry_context", {})
            if ec:
                ec["_buy_timestamp"] = t["timestamp"]
                ec["_buy_price"] = t.get("price")
            buy_map[t["ticker"]].append({
                "timestamp": t["timestamp"],
                "entry_context": ec,
                "price": t.get("price"),
            })

    # Process all sells/partial_sells
    sells = [t for t in trades if t.get("side", "").upper() in ("SELL", "PARTIAL_SELL")]
    print("Processing %d sell records..." % len(sells))

    features_list = []
    matched = 0
    unmatched = 0

    for s in sells:
        ticker = s["ticker"]
        sell_ts = s["timestamp"]

        # Find the most recent BUY before this sell
        candidates = [b for b in buy_map.get(ticker, []) if b["timestamp"] < sell_ts]
        if candidates:
            best_buy = max(candidates, key=lambda x: x["timestamp"])
            ec = best_buy.get("entry_context", {})
            matched += 1
        else:
            ec = {}
            unmatched += 1

        features = build_features_from_trade(s, ec)
        if features.get("pnl_pct") is not None:  # Skip records without pnl
            features_list.append(features)

    print("Matched: %d, Unmatched: %d" % (matched, unmatched))
    print("Valid features generated: %d" % len(features_list))

    # Backup existing JSONL
    if os.path.exists(ML_FEATURES):
        import shutil
        shutil.copy2(ML_FEATURES, ML_FEATURES_BACKUP)
        print("Backed up existing JSONL to %s" % ML_FEATURES_BACKUP)

    # Write new JSONL
    with open(ML_FEATURES, "w") as f:
        for feat in features_list:
            f.write(json.dumps(feat, ensure_ascii=False) + "\n")

    print("Wrote %d records to %s" % (len(features_list), ML_FEATURES))

    # Summary stats
    entry_qualities = defaultdict(int)
    for feat in features_list:
        eq = feat.get("entry_quality", "UNKNOWN")
        entry_qualities[eq] += 1
    print("\nEntry quality distribution:")
    for k, v in sorted(entry_qualities.items()):
        print("  %s: %d (%.0f%%)" % (k, v, v / len(features_list) * 100))

    has_entry_rsi = sum(1 for f in features_list if f.get("entry_rsi") is not None)
    print("\nRecords with entry features: %d/%d (%.0f%%)" % (
        has_entry_rsi, len(features_list), has_entry_rsi / len(features_list) * 100))


if __name__ == "__main__":
    main()
