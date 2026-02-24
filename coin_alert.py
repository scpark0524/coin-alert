"""
🪙 Coin Alert System v1.0 — Upbit KRW 자동매매

v1.0: stock-alert v7.6 로직 기반 코인 자동매매
- 대상: Upbit KRW 마켓 거래량 상위 10종목
- 신호: 1시간봉 기반 3-전략 앙상블 (추세추종 + 평균회귀 + 돌파)
- 레짐: BTC 기준 시장 레짐 감지 → 전략 가중치 + 임계값 동적 조정
- 포지션: inverse-ATR 기반 사이징, 트레일링 스탑, 서킷브레이커
- 백테스트: Walk-Forward (일봉 200일, out-of-sample 검증)
- 실행: GitHub Actions 30분 주기, pyupbit API, 텔레그램 알림
"""

import pyupbit
import pandas as pd
import numpy as np
import requests
import os
import json
import time
from datetime import datetime, timezone, timedelta

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf

# ============================================
# 설정
# ============================================
TICKERS = [
    "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE",
    "KRW-ADA", "KRW-AVAX", "KRW-LINK", "KRW-DOT", "KRW-TRX",
]
INITIAL_CAPITAL = int(os.environ.get("INITIAL_CAPITAL", 3_000_000))  # KRW 300만원 기본

# 캔들 설정
SIGNAL_INTERVAL = "minute60"   # 신호 생성용: 1시간봉
SIGNAL_CANDLES  = 300          # 1시간봉 300개 (~12일)
BT_INTERVAL     = "day"        # 백테스트용: 일봉
BT_CANDLES      = 200          # 일봉 200일

# 기술적 지표
SHORT_WINDOW        = 20
LONG_WINDOW         = 50
RSI_PERIOD          = 14
RSI_OVERBOUGHT      = 75       # 코인: 과열 기준 완화
RSI_OVERSOLD        = 25       # 코인: 침체 기준 완화
MACD_FAST           = 12
MACD_SLOW           = 26
MACD_SIGNAL         = 9
BB_PERIOD           = 20
BB_STD              = 2.5      # 코인: 더 넓은 밴드
ADX_PERIOD          = 14
ADX_STRONG_TREND    = 25
VOLUME_SPIKE_RATIO  = 2.0
PRICE_CHANGE_THRESHOLD = 5.0  # 코인: 5% 이상 급등락
SR_LOOKBACK         = 60
SR_PROXIMITY        = 0.015

# 포지션 사이징
RISK_BUDGET             = 0.02   # 거래당 자본 리스크 2%
MAX_POSITION_PCT        = 0.15   # 종목당 최대 15%
MIN_POSITION_PCT        = 0.05
MAX_PORTFOLIO_EXPOSURE  = 0.80   # 포트폴리오 총 노출 상한 80%

# 켈리 참고용
KELLY_FRACTION          = 0.5
MIN_TRADES_FOR_KELLY    = 10
DEFAULT_WIN_RATE        = 0.55
DEFAULT_WIN_LOSS_RATIO  = 1.5

# 비용 (업비트 수수료 0.05% 매수+매도 = 10bps)
COMMISSION_BPS      = 5
SLIPPAGE_BPS        = 5
TOTAL_COST_BPS      = COMMISSION_BPS + SLIPPAGE_BPS

# ATR 기반 리스크 (코인: 더 넓은 스탑/타겟)
ATR_PERIOD      = 14
ATR_STOP_MULT   = 2.5   # 코인 변동성 반영
ATR_TARGET_MULT = 4.0   # 더 넓은 수익 타겟
MAX_HOLD_DAYS   = 14    # 짧은 보유 주기 (일봉 환산)
SIGNAL_THRESHOLD = 20   # 더 활발한 신호

# 서킷브레이커
CIRCUIT_BREAKER_DD = 0.10  # 포트폴리오 MDD 10% 시 매매 중단

# 파일 경로
_BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE  = os.path.join(_BASE_DIR, "portfolio.json")
ORDER_LOG_FILE  = os.path.join(_BASE_DIR, "order_log.json")

# 환경변수
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")
UPBIT_ACCESS_KEY    = os.environ.get("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY    = os.environ.get("UPBIT_SECRET_KEY")

AUTO_TRADE_ENABLED = all([UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY])


def utc_now():
    return datetime.now(timezone.utc)


# ============================================
# 텔레그램 알림
# ============================================
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ 텔레그램 토큰/챗ID 미설정 — 알림 건너뜀")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ 텔레그램 전송 성공")
        else:
            print(f"❌ 전송 실패: {response.status_code}")
    except Exception as e:
        print(f"❌ 텔레그램 네트워크 오류: {e}")


def send_telegram_photo(image_bytes, caption=""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        if len(caption) > 1024:
            caption = caption[:1020] + "..."
        files = {"photo": ("chart.png", image_bytes, "image/png")}
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"}
        response = requests.post(url, data=data, files=files, timeout=30)
        if response.status_code == 200:
            print("✅ 텔레그램 차트 전송 성공")
        else:
            print(f"❌ 차트 전송 실패: {response.status_code}")
    except Exception as e:
        print(f"❌ 텔레그램 차트 네트워크 오류: {e}")


# ============================================
# 포트폴리오 & 주문 이력
# ============================================
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 포트폴리오 로드 실패: {e}")
    return {}


def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)


def load_order_log():
    if os.path.exists(ORDER_LOG_FILE):
        try:
            with open(ORDER_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_order_log(log):
    with open(ORDER_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def _utc_hour_key():
    """UTC 기준 현재 시간(시간 단위) — 코인 30분 중복 주문 방지용"""
    now = utc_now()
    return now.strftime("%Y-%m-%d-%H")


def has_ordered_this_hour(log, ticker, direction):
    key = f"{ticker}_{direction}"
    return log.get(key) == _utc_hour_key()


def record_order(log, ticker, direction):
    key = f"{ticker}_{direction}"
    log[key] = _utc_hour_key()
    # 오래된 항목 정리 (24시간 이상 된 것)
    cutoff = (utc_now() - timedelta(hours=24)).strftime("%Y-%m-%d-%H")
    stale = [k for k, v in log.items() if v < cutoff]
    for k in stale:
        del log[k]
    save_order_log(log)


# ============================================
# Upbit 자동매매
# ============================================
_upbit_client = None


def get_upbit():
    global _upbit_client
    if _upbit_client is None and AUTO_TRADE_ENABLED:
        try:
            _upbit_client = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
            print("   ✅ Upbit 연결 성공")
        except Exception as e:
            print(f"   ❌ Upbit 연결 실패: {e}")
    return _upbit_client


def execute_buy(ticker, krw_amount):
    """시장가 매수 (KRW 금액 기반)"""
    upbit = get_upbit()
    if not upbit:
        return None
    try:
        resp = upbit.buy_market_order(ticker, krw_amount)
        if resp and resp.get("uuid"):
            print(f"   ✅ 매수 주문 접수: {ticker} ₩{krw_amount:,.0f} (uuid: {resp['uuid'][:8]}...)")
            return resp
        else:
            print(f"   ❌ 매수 주문 실패: {ticker} — {resp}")
            return None
    except Exception as e:
        print(f"   ❌ 매수 주문 오류: {ticker} — {e}")
        return None


def execute_sell(ticker, volume):
    """시장가 매도 (코인 수량 기반)"""
    upbit = get_upbit()
    if not upbit:
        return None
    try:
        resp = upbit.sell_market_order(ticker, volume)
        if resp and resp.get("uuid"):
            print(f"   ✅ 매도 주문 접수: {ticker} {volume} (uuid: {resp['uuid'][:8]}...)")
            return resp
        else:
            print(f"   ❌ 매도 주문 실패: {ticker} — {resp}")
            return None
    except Exception as e:
        print(f"   ❌ 매도 주문 오류: {ticker} — {e}")
        return None


def sync_portfolio_with_upbit(portfolio):
    """pyupbit.get_balances()로 실계좌와 포트폴리오 동기화"""
    if not AUTO_TRADE_ENABLED:
        return load_portfolio()
    upbit = get_upbit()
    if not upbit:
        return load_portfolio()
    print("🔄 실계좌 잔고 동기화 중...")
    try:
        balances = upbit.get_balances()
        actual = {}
        for b in balances:
            currency = b.get("currency", "")
            ticker = f"KRW-{currency}"
            volume = float(b.get("balance", 0)) + float(b.get("locked", 0))
            avg_price = float(b.get("avg_buy_price", 0))
            if ticker in TICKERS and volume > 0:
                actual[ticker] = {
                    "volume": volume,
                    "entry_price": avg_price,
                    "entry_date": "synced",
                }
        local = load_portfolio()
        # high_watermark, trailing_stop 보존
        for t in actual:
            if t in local:
                for key in ("high_watermark", "trailing_stop", "entry_date"):
                    if key in local[t]:
                        actual[t][key] = local[t][key]
            if "high_watermark" not in actual[t]:
                actual[t]["high_watermark"] = actual[t]["entry_price"]
        # _meta 보존
        if "_meta" in local:
            actual["_meta"] = local["_meta"]

        local_set = {k for k in local if k != "_meta"}
        actual_set = set(actual.keys()) - {"_meta"}
        if actual_set != local_set:
            diff = f"로컬{sorted(local_set)} → 실계좌{sorted(actual_set)}"
            print(f"   ⚠️ 불일치 감지: {diff}")
            send_telegram(f"⚠️ 포트폴리오 동기화: {diff}")
        else:
            holdings = sorted(actual_set) if actual_set else ["보유 없음"]
            print(f"   ✅ 동기화 완료: {holdings}")
        save_portfolio(actual)
        return actual
    except Exception as e:
        print(f"   ⚠️ 동기화 실패 (로컬 파일 사용): {e}")
        return load_portfolio()


def fetch_actual_capital():
    """pyupbit.get_balance("KRW")로 현금 잔고 조회"""
    if not AUTO_TRADE_ENABLED:
        return INITIAL_CAPITAL
    upbit = get_upbit()
    if not upbit:
        return INITIAL_CAPITAL
    try:
        krw = upbit.get_balance("KRW")
        if krw and krw > 0:
            print(f"   💰 실계좌 가용 KRW: ₩{krw:,.0f}")
            return krw
    except Exception as e:
        print(f"   ⚠️ 잔고 조회 실패 (기본값 ₩{INITIAL_CAPITAL:,} 사용): {e}")
    return INITIAL_CAPITAL


# ============================================
# 서킷브레이커
# ============================================
def check_circuit_breaker(portfolio, capital, results):
    """포트폴리오 MDD 10% 이상 시 매매 중단"""
    meta = portfolio.get("_meta", {})
    current_value = capital
    priced_tickers = set()
    for r in results:
        ticker = r["ticker"]
        if r["signal"] != "NO_DATA" and ticker in portfolio and ticker != "_meta":
            pos = portfolio[ticker]
            current_value += r["price"] * pos.get("volume", 0)
            priced_tickers.add(ticker)
    for ticker in portfolio:
        if ticker != "_meta" and ticker not in priced_tickers:
            pos = portfolio[ticker]
            current_value += pos.get("entry_price", 0) * pos.get("volume", 0)
    peak_value = meta.get("peak_value", current_value)
    if current_value > peak_value:
        meta["peak_value"] = current_value
        meta["peak_date"] = utc_now().strftime("%Y-%m-%d")
        peak_value = current_value
    drawdown = (peak_value - current_value) / peak_value if peak_value > 0 else 0
    meta["version"] = "1.0"
    meta["last_value"] = round(current_value, 0)
    meta["last_check"] = utc_now().strftime("%Y-%m-%d %H:%M")
    portfolio["_meta"] = meta
    if drawdown >= CIRCUIT_BREAKER_DD:
        return True, drawdown, peak_value
    return False, drawdown, peak_value


# ============================================
# 상관관계 기반 노출 패널티
# ============================================
def calc_correlation_penalty(tickers_in_portfolio, all_price_data):
    if len(tickers_in_portfolio) < 2:
        return 1.0
    returns = pd.DataFrame()
    for ticker in tickers_in_portfolio:
        if ticker in all_price_data and len(all_price_data[ticker]) > 0:
            close = all_price_data[ticker]["Close"]
            returns[ticker] = close.pct_change().dropna()
    if len(returns.columns) < 2:
        return 1.0
    corr_matrix = returns.tail(60).corr()
    n = len(corr_matrix)
    total_corr = 0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            val = corr_matrix.iloc[i, j]
            if pd.notna(val):
                total_corr += abs(val)
                count += 1
    avg_corr = total_corr / count if count > 0 else 0
    penalty = 1.0 + avg_corr * 0.5
    return penalty


# ============================================
# 공포탐욕 지수 (코인 전용: alternative.me)
# ============================================
def get_crypto_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        if r.status_code == 200:
            d = r.json()["data"][0]
            return {"score": int(d["value"]), "rating": d["value_classification"]}
    except Exception as e:
        print(f"⚠️ 코인 공포탐욕 조회 실패: {e}")
    return None


def format_fear_greed(fg):
    if not fg:
        return "❓ 조회 실패"
    s = fg["score"]
    if s <= 25:  return f"😱 {s}/100 (극도의 공포)"
    elif s <= 45: return f"😰 {s}/100 (공포)"
    elif s <= 55: return f"😐 {s}/100 (중립)"
    elif s <= 75: return f"😀 {s}/100 (탐욕)"
    else:         return f"🤑 {s}/100 (극도의 탐욕)"


# ============================================
# 데이터 조회 (pyupbit)
# ============================================
def get_upbit_ohlcv(ticker, interval=SIGNAL_INTERVAL, count=SIGNAL_CANDLES):
    """pyupbit로 OHLCV 조회. DataFrame(Open/High/Low/Close/Volume) 반환."""
    for attempt in range(3):
        try:
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
            if df is not None and len(df) >= 10:
                df.columns = [c.capitalize() for c in df.columns]
                df.index = pd.to_datetime(df.index)
                return df.dropna()
        except Exception as e:
            if attempt < 2:
                time.sleep(0.5)
            else:
                print(f"   ⚠️ {ticker} 데이터 조회 실패: {e}")
    return None


def fetch_all_data():
    """전 종목 신호용(1H) + 백테스트용(일봉) 데이터 조회"""
    signal_data = {}
    bt_data = {}
    for ticker in TICKERS:
        df_signal = get_upbit_ohlcv(ticker, SIGNAL_INTERVAL, SIGNAL_CANDLES)
        if df_signal is not None:
            signal_data[ticker] = df_signal
        time.sleep(0.12)  # rate limit 준수
        df_bt = get_upbit_ohlcv(ticker, BT_INTERVAL, BT_CANDLES)
        if df_bt is not None:
            bt_data[ticker] = df_bt
        time.sleep(0.12)
    print(f"   ✅ 신호 데이터: {len(signal_data)}/{len(TICKERS)}종목")
    print(f"   ✅ 백테스트 데이터: {len(bt_data)}/{len(TICKERS)}종목")
    return signal_data, bt_data


# ============================================
# 기술적 지표
# ============================================
def calc_rsi(series, period=RSI_PERIOD):
    d = series.diff()
    g = d.where(d > 0, 0).rolling(period).mean()
    l_val = (-d.where(d < 0, 0)).rolling(period).mean()
    return 100 - (100 / (1 + g / l_val))


def calc_macd(series, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL):
    ef = series.ewm(span=fast, adjust=False).mean()
    es = series.ewm(span=slow, adjust=False).mean()
    ml = ef - es
    sl = ml.ewm(span=signal, adjust=False).mean()
    return ml, sl, ml - sl


def calc_bollinger(series, period=BB_PERIOD, std=BB_STD):
    sma = series.rolling(period).mean()
    sd = series.rolling(period).std()
    return sma + sd * std, sma, sma - sd * std


def calc_adx(data, period=ADX_PERIOD):
    h, l_val, c = data["High"], data["Low"], data["Close"]
    tr = pd.concat([h - l_val, abs(h - c.shift(1)), abs(l_val - c.shift(1))], axis=1).max(axis=1)
    um = h - h.shift(1)
    dm_val = l_val.shift(1) - l_val
    pdm = pd.Series(0.0, index=data.index)
    ndm = pd.Series(0.0, index=data.index)
    pdm[(um > dm_val) & (um > 0)] = um[(um > dm_val) & (um > 0)]
    ndm[(dm_val > um) & (dm_val > 0)] = dm_val[(dm_val > um) & (dm_val > 0)]
    atr = tr.rolling(period).mean()
    pdi = 100 * pdm.rolling(period).mean() / atr
    ndi = 100 * ndm.rolling(period).mean() / atr
    dx = 100 * abs(pdi - ndi) / (pdi + ndi)
    return dx.rolling(period).mean(), pdi, ndi


def calc_atr(data, period=ATR_PERIOD):
    h, l_val, c = data["High"], data["Low"], data["Close"]
    tr = pd.concat([h - l_val, abs(h - c.shift(1)), abs(l_val - c.shift(1))], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_support_resistance(data, lookback=SR_LOOKBACK):
    rec = data.tail(lookback)
    hs, ls = rec["High"].values, rec["Low"].values
    cp = float(data["Close"].iloc[-1])
    last = data.iloc[-1]
    pv = (float(last["High"]) + float(last["Low"]) + float(last["Close"])) / 3
    r1 = 2 * pv - float(last["Low"])
    s1 = 2 * pv - float(last["High"])
    sh, sl_list = [], []
    w = 3
    for i in range(w, len(rec) - w):
        if hs[i] == max(hs[i - w:i + w + 1]):
            sh.append(hs[i])
        if ls[i] == min(ls[i - w:i + w + 1]):
            sl_list.append(ls[i])

    def cluster(lvls, th=0.01):
        if not lvls:
            return []
        lvls = sorted(lvls)
        cl = [[lvls[0]]]
        for v in lvls[1:]:
            if (v - cl[-1][-1]) / cl[-1][-1] < th:
                cl[-1].append(v)
            else:
                cl.append([v])
        return [np.mean(c) for c in cl]

    rl, spl = cluster(sh), cluster(sl_list)
    nr = next((v for v in sorted(rl) if v > cp), r1)
    ns = next((v for v in sorted(spl, reverse=True) if v < cp), s1)
    return {
        "resistance": nr, "support": ns,
        "near_resistance": abs(cp - nr) / cp < SR_PROXIMITY,
        "near_support": abs(cp - ns) / cp < SR_PROXIMITY,
    }


def calc_weekly_signals(data):
    """주봉 대신 일봉 기반 중기 추세 (코인: 주봉 별도 없이 일봉 활용)"""
    if data is None or len(data) < 22:
        return {"trend": "UNKNOWN", "rsi": None, "ma_signal": "UNKNOWN"}
    c = data["Close"]
    ss = c.rolling(10).mean()
    sl = c.rolling(20).mean()
    rsi = calc_rsi(c)
    t, y = {"SS": float(ss.iloc[-1]), "SL": float(sl.iloc[-1]), "RSI": float(rsi.iloc[-1])}, \
           {"SS": float(ss.iloc[-2]), "SL": float(sl.iloc[-2])}
    tr = "UP" if t["SS"] > t["SL"] else "DOWN"
    ma = "HOLD"
    if y["SS"] <= y["SL"] and t["SS"] > t["SL"]:
        ma = "BUY"
    elif y["SS"] >= y["SL"] and t["SS"] < t["SL"]:
        ma = "SELL"
    return {"trend": tr, "rsi": t["RSI"], "ma_signal": ma}


# ============================================
# 시장 레짐 감지 (BTC 기준)
# ============================================
def detect_market_regime(btc_data):
    c = btc_data["Close"]
    s50  = c.rolling(50).mean()
    s200 = c.rolling(200).mean()
    # 코인: 1H봉 기준 변동성 → 연율화 (24*365)
    vol20 = c.pct_change().tail(20).std() * np.sqrt(24 * 365) * 100
    p    = float(c.iloc[-1])
    sv50 = float(s50.iloc[-1])
    sv200 = float(s200.iloc[-1]) if pd.notna(s200.iloc[-1]) else sv50
    adx_s, _, _ = calc_adx(btc_data)
    av = float(adx_s.iloc[-1]) if pd.notna(adx_s.iloc[-1]) else 15
    a50, a200, st = p > sv50, p > sv200, av >= ADX_STRONG_TREND
    # 코인은 변동성이 기본적으로 높으므로 VOLATILE 기준을 높임
    if vol20 > 80 and not st:
        regime = "VOLATILE"
    elif a50 and a200 and st:
        regime = "BULL"
    elif not a50 and not a200 and st:
        regime = "BEAR"
    elif a50 and a200:
        regime = "MILD_BULL"
    elif not a50 and not a200:
        regime = "MILD_BEAR"
    else:
        regime = "SIDEWAYS"
    return {"regime": regime, "adx": av, "vol_20": vol20, "above_sma50": a50, "above_sma200": a200}


def get_regime_emoji(r):
    return {
        "BULL": "🟢 강한 상승장", "MILD_BULL": "🟡 약한 상승장",
        "SIDEWAYS": "⚪ 횡보장", "MILD_BEAR": "🟠 약한 하락장",
        "BEAR": "🔴 강한 하락장", "VOLATILE": "🌪️ 고변동성",
    }.get(r, r)


def get_regime_threshold(r):
    """레짐별 신호 임계값 (코인: 전반적으로 낮게 설정)"""
    return {
        "BULL":      24,
        "MILD_BULL": 20,
        "SIDEWAYS":  16,
        "MILD_BEAR": 18,
        "BEAR":      24,
        "VOLATILE":  18,
    }.get(r, SIGNAL_THRESHOLD)


def get_regime_strategy_weights(r):
    return {
        "BULL":      {"trend": 0.30, "mean_revert": 0.10, "breakout": 0.60},
        "MILD_BULL": {"trend": 0.25, "mean_revert": 0.15, "breakout": 0.60},
        "SIDEWAYS":  {"trend": 0.15, "mean_revert": 0.40, "breakout": 0.45},
        "MILD_BEAR": {"trend": 0.15, "mean_revert": 0.25, "breakout": 0.60},
        "BEAR":      {"trend": 0.10, "mean_revert": 0.30, "breakout": 0.60},
        "VOLATILE":  {"trend": 0.10, "mean_revert": 0.20, "breakout": 0.70},
    }.get(r, {"trend": 0.20, "mean_revert": 0.20, "breakout": 0.60})


# ============================================
# 멀티 전략 앙상블
# ============================================
def strategy_trend_following(data, today, yesterday):
    score = 0
    if yesterday["SMA_Short"] <= yesterday["SMA_Long"] and today["SMA_Short"] > today["SMA_Long"]:
        score += 40
    elif yesterday["SMA_Short"] >= yesterday["SMA_Long"] and today["SMA_Short"] < today["SMA_Long"]:
        score -= 40
    elif today["SMA_Short"] > today["SMA_Long"]:
        score += 15
    else:
        score -= 15
    if yesterday["MACD"] <= yesterday["MACD_Signal"] and today["MACD"] > today["MACD_Signal"]:
        score += 30
    elif yesterday["MACD"] >= yesterday["MACD_Signal"] and today["MACD"] < today["MACD_Signal"]:
        score -= 30
    elif today["MACD_Hist"] > 0:
        score += 10
    else:
        score -= 10
    if today["ADX"] >= ADX_STRONG_TREND:
        score += 30 if today["Plus_DI"] > today["Minus_DI"] else -30
    return max(-100, min(100, score))


def strategy_mean_reversion(data, today):
    score = 0
    rsi = float(today["RSI"])
    p = float(today["Close"])
    if rsi <= RSI_OVERSOLD:      score += 50
    elif rsi <= 30:              score += 35
    elif rsi <= 40:              score += 15
    elif rsi >= RSI_OVERBOUGHT:  score -= 50
    elif rsi >= 70:              score -= 35
    elif rsi >= 60:              score -= 15
    bu = float(today["BB_Upper"])
    bl = float(today["BB_Lower"])
    bm = float(today["BB_Mid"])
    if p <= bl:                          score += 40
    elif p <= bm - (bm - bl) * 0.5:     score += 20
    elif p >= bu:                        score -= 40
    elif p >= bm + (bu - bm) * 0.5:     score -= 20
    sr = calc_support_resistance(data)
    if sr["near_support"]:    score += 10
    if sr["near_resistance"]: score -= 10
    return max(-100, min(100, score))


def strategy_breakout(data, today):
    score = 0
    c = data["Close"]
    p = float(today["Close"])
    # 코인: 52주 대신 300캔들(~12일 1H 기준) 고점/저점
    c_all = c
    h_max, l_min = float(c_all.max()), float(c_all.min())
    if p >= h_max * 0.98:
        score += 40
    elif p <= l_min * 1.02:
        score -= 40
    elif len(c) >= 50 and p >= float(c.tail(50).max()) * 0.99:
        score += 25
    elif len(c) >= 50 and p <= float(c.tail(50).min()) * 1.01:
        score -= 25
    elif len(c) >= 20 and p >= float(c.tail(20).max()):
        score += 15
    elif len(c) >= 20 and p <= float(c.tail(20).min()):
        score -= 15
    av = data["Volume"].rolling(20).mean().iloc[-1]
    vr = float(today["Volume"]) / float(av) if float(av) > 0 else 1
    dc = (p / float(data["Close"].iloc[-2]) - 1) * 100
    if vr >= 2:   score += 30 if dc > 0 else -30
    elif vr >= 1.5: score += 15 if dc > 0 else -15
    if p > float(today["BB_Upper"]): score += 30
    elif p < float(today["BB_Lower"]): score -= 30
    return max(-100, min(100, score))


def ensemble_signal(t, m, b, w):
    return t * w["trend"] + m * w["mean_revert"] + b * w["breakout"]


# ============================================
# 백테스팅 (일봉 기반 Walk-Forward)
# ============================================
def quick_backtest(data, rw, btc_data=None, return_trades=False):
    c = data["Close"]
    data = data.copy()
    data["SMA_Short"] = c.rolling(SHORT_WINDOW).mean()
    data["SMA_Long"]  = c.rolling(LONG_WINDOW).mean()
    data["RSI"]       = calc_rsi(c)
    data["MACD"], data["MACD_Signal"], data["MACD_Hist"] = calc_macd(c)
    data["BB_Upper"], data["BB_Mid"], data["BB_Lower"]   = calc_bollinger(c)
    data["ADX"], data["Plus_DI"], data["Minus_DI"]       = calc_adx(data)
    data["ATR"] = calc_atr(data)

    cost_pct = TOTAL_COST_BPS / 10000
    trades = []
    pos = None

    for i in range(LONG_WINDOW + 2, len(data) - 1):
        t_bar = data.iloc[i]
        y_bar = data.iloc[i - 1]
        next_open = float(data.iloc[i + 1]["Open"])
        sd = data.iloc[:i + 1]

        current_rw = rw
        current_threshold = SIGNAL_THRESHOLD
        if btc_data is not None:
            bar_date = data.index[i]
            btc_slice = btc_data.loc[:bar_date]
            if len(btc_slice) >= 200:
                try:
                    ri_t = detect_market_regime(btc_slice)
                    current_rw = get_regime_strategy_weights(ri_t["regime"])
                    current_threshold = get_regime_threshold(ri_t["regime"])
                except Exception:
                    pass

        total = ensemble_signal(
            strategy_trend_following(sd, t_bar, y_bar),
            strategy_mean_reversion(sd, t_bar),
            strategy_breakout(sd, t_bar),
            current_rw,
        )

        atr_val = float(t_bar["ATR"]) if pd.notna(t_bar["ATR"]) else 0

        if pos is None:
            if total >= current_threshold:
                entry_price = next_open * (1 + cost_pct)
                stop_loss   = entry_price - atr_val * ATR_STOP_MULT if atr_val > 0 else entry_price * 0.92
                take_profit = entry_price + atr_val * ATR_TARGET_MULT if atr_val > 0 else entry_price * 1.15
                pos = {"entry": entry_price, "idx": i + 1, "stop": stop_loss, "target": take_profit, "high": entry_price}
        else:
            hold_days = i - pos["idx"]
            bar_high = float(t_bar["High"])
            bar_low  = float(t_bar["Low"])
            if bar_high > pos["high"]:
                pos["high"] = bar_high
                pos["stop"] = max(pos["stop"], pos["high"] - atr_val * ATR_STOP_MULT) if atr_val > 0 else pos["stop"]

            exit_reason = None
            exit_price  = None
            if bar_low <= pos["stop"]:
                exit_reason = "STOP_LOSS"
                exit_price  = pos["stop"] * (1 - cost_pct)
            elif bar_high >= pos["target"]:
                exit_reason = "TAKE_PROFIT"
                exit_price  = pos["target"] * (1 - cost_pct)
            elif hold_days >= MAX_HOLD_DAYS:
                exit_reason = "TIME_STOP"
                exit_price  = next_open * (1 - cost_pct)
            elif total <= -10:
                exit_reason = "SIGNAL_EXIT"
                exit_price  = next_open * (1 - cost_pct)

            if exit_reason:
                pnl = (exit_price / pos["entry"] - 1) * 100
                trades.append({"pnl": pnl, "days": hold_days, "reason": exit_reason, "entry_idx": pos["idx"]})
                pos = None

    if pos:
        exit_price = float(data["Close"].iloc[-1]) * (1 - cost_pct)
        pnl = (exit_price / pos["entry"] - 1) * 100
        trades.append({"pnl": pnl, "days": len(data) - pos["idx"], "reason": "OPEN", "entry_idx": pos["idx"]})

    empty = {
        "win_rate": DEFAULT_WIN_RATE, "wl_ratio": DEFAULT_WIN_LOSS_RATIO,
        "total_trades": 0, "avg_pnl": 0, "use_kelly": False,
        "sharpe": 0, "max_dd": 0, "calmar": 0, "total_return": 0,
    }
    if not trades:
        return empty

    wins   = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    wr = len(wins) / len(trades)
    aw = np.mean([t["pnl"] for t in wins])   if wins   else 1
    al = abs(np.mean([t["pnl"] for t in losses])) if losses else 1
    use_kelly = len(trades) >= MIN_TRADES_FOR_KELLY

    pnl_series  = pd.Series([t["pnl"] for t in trades])
    avg_holding = np.mean([t["days"] for t in trades])
    trades_per_year = 365 / avg_holding if avg_holding > 0 else 12
    sharpe = (pnl_series.mean() / pnl_series.std() * np.sqrt(trades_per_year)
              if pnl_series.std() > 0 else 0)
    cumulative  = (1 + pnl_series / 100).cumprod()
    peak        = cumulative.cummax()
    drawdown    = (cumulative - peak) / peak
    max_dd      = float(drawdown.min()) * 100
    total_return = float((cumulative.iloc[-1] - 1) * 100)
    total_days  = sum(t["days"] for t in trades)
    annual_return = total_return * (365 / total_days) if total_days > 0 else 0
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

    result = {
        "win_rate": wr, "wl_ratio": aw / al if al > 0 else DEFAULT_WIN_LOSS_RATIO,
        "total_trades": len(trades), "wins": len(wins), "losses": len(losses),
        "avg_pnl": np.mean([t["pnl"] for t in trades]),
        "avg_win": aw if wins else 0, "avg_loss": al if losses else 0,
        "use_kelly": use_kelly, "sharpe": round(sharpe, 2),
        "max_dd": round(max_dd, 1), "calmar": round(calmar, 2),
        "total_return": round(total_return, 1),
    }
    if return_trades:
        result["_trades"] = trades
    return result


def walk_forward_backtest(data, rw, btc_data=None):
    """Walk-forward out-of-sample 백테스트. 150일 train + 50일 test."""
    total_bars = len(data)
    train_bars = 150
    test_bars  = 50
    min_required = train_bars + test_bars

    if total_bars < min_required:
        return quick_backtest(data, rw, btc_data)

    n_windows = max(1, (total_bars - train_bars) // test_bars)
    all_test_trades = []

    for w in range(n_windows):
        window_start = w * test_bars
        window_end   = min(window_start + train_bars + test_bars, total_bars)
        window_data  = data.iloc[window_start:window_end].copy()

        bt_slice = btc_data.iloc[window_start:window_end].copy() if btc_data is not None else None
        wf_bt = quick_backtest(window_data, rw, bt_slice, return_trades=True)
        test_trades = [t for t in wf_bt.get("_trades", []) if t["entry_idx"] >= train_bars]
        all_test_trades.extend(test_trades)

    if not all_test_trades:
        return quick_backtest(data, rw, btc_data)

    wins   = [t for t in all_test_trades if t["pnl"] > 0]
    losses = [t for t in all_test_trades if t["pnl"] <= 0]
    wr = len(wins) / len(all_test_trades)
    aw = np.mean([t["pnl"] for t in wins])   if wins   else 1
    al = abs(np.mean([t["pnl"] for t in losses])) if losses else 1
    pnl_series  = pd.Series([t["pnl"] for t in all_test_trades])
    avg_holding = np.mean([t["days"] for t in all_test_trades])
    trades_per_year = 365 / avg_holding if avg_holding > 0 else 12
    sharpe = (pnl_series.mean() / pnl_series.std() * np.sqrt(trades_per_year)
              if pnl_series.std() > 0 else 0)
    cumulative = (1 + pnl_series / 100).cumprod()
    peak       = cumulative.cummax()
    max_dd     = float(((cumulative - peak) / peak).min()) * 100
    total_return = float((cumulative.iloc[-1] - 1) * 100)
    total_days   = sum(t["days"] for t in all_test_trades)
    annual_return = total_return * (365 / total_days) if total_days > 0 else 0
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

    return {
        "win_rate": wr, "wl_ratio": aw / al if al > 0 else DEFAULT_WIN_LOSS_RATIO,
        "total_trades": len(all_test_trades), "wins": len(wins), "losses": len(losses),
        "avg_pnl": float(pnl_series.mean()),
        "avg_win": aw if wins else 0, "avg_loss": al if losses else 0,
        "use_kelly": len(all_test_trades) >= MIN_TRADES_FOR_KELLY,
        "sharpe": round(sharpe, 2), "max_dd": round(max_dd, 1),
        "calmar": round(calmar, 2), "total_return": round(total_return, 1),
    }


# ============================================
# 포지션 사이징 (inverse-ATR 기반)
# ============================================
def calc_position_size(atr_val, price, conf, bt, capital=INITIAL_CAPITAL):
    if price <= 0 or atr_val <= 0:
        return {"position_pct": 0, "position_krw": 0, "method": "SKIP", "kelly_ref": 0}
    if conf < 40:
        return {"position_pct": 0, "position_krw": 0, "method": "SKIP", "kelly_ref": 0}
    if bt.get("total_trades", 0) >= 5 and bt.get("sharpe", 0) < 0:
        return {"position_pct": 0, "position_krw": 0, "method": "BT_REJECT", "kelly_ref": 0}

    atr_pct  = atr_val / price
    raw_pct  = RISK_BUDGET / (atr_pct * ATR_STOP_MULT)
    conf_mult = 1.0 if conf >= 80 else 0.7 if conf >= 60 else 0.4
    raw_pct  *= conf_mult
    position_pct = max(MIN_POSITION_PCT, min(MAX_POSITION_PCT, raw_pct))

    kelly_ref = 0
    if bt.get("use_kelly"):
        wr, wlr = bt["win_rate"], bt["wl_ratio"]
        kelly_ref = max(0, wr - (1 - wr) / wlr) * KELLY_FRACTION if wlr > 0 else 0

    return {
        "position_pct": position_pct * 100,
        "position_krw": capital * position_pct,
        "method": "INV_ATR",
        "kelly_ref": round(kelly_ref * 100, 1),
        "atr_pct": round(atr_pct * 100, 2),
    }


# ============================================
# 종합 분석
# ============================================
def analyze_ticker(ticker, data, regime_info, regime_weights, fear_greed,
                   btc_data=None, backtest_data=None):
    if len(data) < LONG_WINDOW + 2:
        return {"ticker": ticker, "signal": "NO_DATA"}

    c = data["Close"]
    data = data.copy()
    data["SMA_Short"] = c.rolling(SHORT_WINDOW).mean()
    data["SMA_Long"]  = c.rolling(LONG_WINDOW).mean()
    data["RSI"]       = calc_rsi(c)
    data["MACD"], data["MACD_Signal"], data["MACD_Hist"] = calc_macd(c)
    data["BB_Upper"], data["BB_Mid"], data["BB_Lower"]   = calc_bollinger(c)
    data["ADX"], data["Plus_DI"], data["Minus_DI"]       = calc_adx(data)
    data["ATR"] = calc_atr(data)

    t, y = data.iloc[-1], data.iloc[-2]
    cp  = float(t["Close"])
    dc  = (cp / float(y["Close"]) - 1) * 100
    rsi = float(t["RSI"])
    rs  = "과매수 ⚠️" if rsi >= RSI_OVERBOUGHT else "과매도 🔥" if rsi <= RSI_OVERSOLD else "중립"
    bs  = "상단 돌파 ⚠️" if cp >= float(t["BB_Upper"]) else "하단 이탈 🔥" if cp <= float(t["BB_Lower"]) else "밴드 내"
    adx   = float(t["ADX"]) if pd.notna(t["ADX"]) else 0
    pdi   = float(t["Plus_DI"]) if pd.notna(t["Plus_DI"]) else 0
    ndi   = float(t["Minus_DI"]) if pd.notna(t["Minus_DI"]) else 0
    atr_val = float(t["ATR"]) if pd.notna(t["ATR"]) else 0
    av    = data["Volume"].rolling(20).mean().iloc[-1]
    vr    = float(t["Volume"]) / float(av) if float(av) > 0 else 0
    sr    = calc_support_resistance(data)

    ts  = strategy_trend_following(data, t, y)
    ms  = strategy_mean_reversion(data, t)
    bks = strategy_breakout(data, t)
    es  = ensemble_signal(ts, ms, bks, regime_weights)

    threshold = get_regime_threshold(regime_info["regime"])

    if es >= 50:         sig = "STRONG_BUY"
    elif es >= threshold: sig = "BUY"
    elif es <= -50:       sig = "STRONG_CLOSE"
    elif es <= -threshold: sig = "CLOSE"
    else:                  sig = "HOLD"

    bt_src = backtest_data if backtest_data is not None else data.copy()
    bt = walk_forward_backtest(bt_src, regime_weights, btc_data)

    wk = calc_weekly_signals(backtest_data)

    if abs(es) >= threshold:
        conf = min(100, 40 + (abs(es) - threshold) * 2)
    else:
        conf = max(0, abs(es) * 40 / threshold) if threshold > 0 else 0
    if bt.get("total_trades", 0) >= 5:
        bt_sharpe = bt.get("sharpe", 0)
        if bt_sharpe >= 1.5:  conf = min(100, conf + 15)
        elif bt_sharpe >= 0.5: conf = min(100, conf + 10)
        if bt.get("win_rate", 0) > 0.50: conf = min(100, conf + 10)
    if wk["trend"] != "UNKNOWN":
        if (es > 0 and wk["trend"] == "UP") or (es < 0 and wk["trend"] == "DOWN"):
            conf = min(100, conf + 10)
        else:
            conf = max(0, conf - 10)
    if fear_greed:
        fg = fear_greed["score"]
        if (es > 0 and fg <= 30) or (es < 0 and fg >= 70):
            conf = min(100, conf + 5)

    stop_loss   = cp - atr_val * ATR_STOP_MULT   if atr_val > 0 else cp * 0.92
    take_profit = cp + atr_val * ATR_TARGET_MULT  if atr_val > 0 else cp * 1.15

    ps = calc_position_size(atr_val, cp, conf, bt)

    return {
        "ticker": ticker, "signal": sig, "price": cp, "daily_change": dc,
        "sma_short": float(t["SMA_Short"]) if pd.notna(t["SMA_Short"]) else cp,
        "sma_long":  float(t["SMA_Long"])  if pd.notna(t["SMA_Long"]) else cp,
        "rsi": rsi, "rsi_status": rs, "macd_hist": float(t["MACD_Hist"]),
        "bb_status": bs, "bb_upper": float(t["BB_Upper"]), "bb_lower": float(t["BB_Lower"]),
        "adx": adx, "adx_trend": "상승" if pdi > ndi else "하락",
        "atr": atr_val, "stop_loss": stop_loss, "take_profit": take_profit,
        "volume_ratio": vr, "volume_spike": vr >= VOLUME_SPIKE_RATIO,
        "price_high": float(c.max()), "price_low": float(c.min()),
        "is_surge": abs(dc) >= PRICE_CHANGE_THRESHOLD,
        "support": sr["support"], "resistance": sr["resistance"],
        "near_support": sr["near_support"], "near_resistance": sr["near_resistance"],
        "trend_score": ts, "mean_rev_score": ms, "breakout_score": bks,
        "ensemble_score": es, "confidence": conf,
        "backtest": bt, "weekly": wk, "position": ps,
    }


# ============================================
# 메시지 포맷
# ============================================
def get_score_grade(s):
    if s >= 80:   return "🅰️"
    elif s >= 60: return "🅱️"
    elif s >= 40: return "🅲"
    elif s >= 20: return "🅳"
    else:         return "🅴"


def _fmt_krw(v):
    if v >= 1_000_000:   return f"₩{v/1_000_000:.2f}M"
    elif v >= 1_000:     return f"₩{v/1_000:.1f}K"
    else:                return f"₩{v:,.0f}"


def format_signal_message(r):
    s = r["signal"]
    if s == "STRONG_BUY":   h = "🟢🟢🟢 <b>강력 매수</b>"
    elif s == "BUY":        h = "🟢 <b>매수 신호</b>"
    elif s == "STRONG_CLOSE": h = "🔴🔴🔴 <b>강력 청산</b>"
    elif s == "CLOSE":      h = "🔴 <b>청산 신호</b>"
    else: return None

    ps, bt = r["position"], r["backtest"]
    ticker_name = r["ticker"].replace("KRW-", "")
    msg = f"""{h} — <b>{ticker_name}</b>
💰 {_fmt_krw(r['price'])} ({r['daily_change']:+.1f}%)
🎯 신뢰도: {r['confidence']}/100 {get_score_grade(r['confidence'])}"""

    if "BUY" in s:
        msg += f"""
💵 추천 투자: {_fmt_krw(ps['position_krw'])} ({ps['position_pct']:.0f}%) [{ps['method']}]
🛡️ 손절: {_fmt_krw(r['stop_loss'])} | 익절: {_fmt_krw(r['take_profit'])}"""

    msg += f"""
📊 지지 {_fmt_krw(r['support'])} | 저항 {_fmt_krw(r['resistance'])}
📈 백테스트({bt['total_trades']}회): 승률 {bt['win_rate']*100:.0f}% 평균{bt['avg_pnl']:+.1f}%
📐 Sharpe {bt['sharpe']:.1f} | MDD {bt['max_dd']:.0f}% | Calmar {bt['calmar']:.1f}"""

    al = []
    if r["volume_spike"]: al.append(f"거래량 {r['volume_ratio']:.1f}x")
    if r["is_surge"]:     al.append("급등" if r["daily_change"] > 0 else "급락")
    if al: msg += "\n⚠️ " + " | ".join(al)

    return msg


def format_status_message(results, regime_info, fear_greed):
    now = utc_now().strftime('%Y-%m-%d %H:%M')
    msg = f"🪙 <b>코인 리포트 v1.0</b> ({now} UTC)\n"
    msg += f"🧠 공포탐욕: {format_fear_greed(fear_greed)}\n"
    msg += f"🌍 시장(BTC): {get_regime_emoji(regime_info['regime'])}\n"

    for r in results:
        if r["signal"] == "NO_DATA":
            msg += f"\n⚠️ {r['ticker']}: 데이터 없음"
            continue
        tr   = "📈" if r["sma_short"] > r["sma_long"] else "📉"
        es   = r["ensemble_score"]
        name = r["ticker"].replace("KRW-", "")
        if es > 0:   d = f"매수 {r['confidence']}점"
        elif es < 0: d = f"청산 {r['confidence']}점"
        else:        d = "중립"

        msg += f"\n{tr} <b>{name}</b> {_fmt_krw(r['price'])} ({r['daily_change']:+.1f}%)"
        msg += f"\n   {r['signal']} ({d})"

        fl = []
        if r["volume_spike"]:    fl.append("거래량↑")
        if r["is_surge"]:        fl.append("급변동")
        if r["near_support"]:    fl.append("지지근접")
        if r["near_resistance"]: fl.append("저항근접")
        if fl: msg += f" 🚩 {', '.join(fl)}"

    return msg


# ============================================
# 차트 생성
# ============================================
def generate_chart(ticker, data, result):
    try:
        df = data.tail(60).copy()
        if len(df) < 20:
            return None

        mc = mpf.make_marketcolors(
            up="#26a69a", down="#ef5350", edge="inherit", wick="inherit",
            volume={"up": "#26a69a80", "down": "#ef535080"},
        )
        style = mpf.make_mpf_style(
            marketcolors=mc, facecolor="#1e1e2e", edgecolor="#1e1e2e",
            figcolor="#1e1e2e", gridcolor="#333344", gridstyle="--", y_on_right=True,
            rc={"axes.labelcolor": "#ccc", "xtick.color": "#999", "ytick.color": "#999"},
        )

        close = df["Close"]
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(min(50, len(close))).mean()
        bb_u, _, bb_l = calc_bollinger(close, period=min(20, len(close)))
        rsi   = calc_rsi(close, period=min(14, len(close) - 1))

        ap = [
            mpf.make_addplot(sma20, color="#ffd700", width=1.0),
            mpf.make_addplot(sma50, color="#00bcd4", width=1.0),
            mpf.make_addplot(bb_u,  color="#666666", width=0.7, linestyle="--"),
            mpf.make_addplot(bb_l,  color="#666666", width=0.7, linestyle="--"),
            mpf.make_addplot(rsi, panel=2, color="#ba68c8", width=1.2, ylabel="RSI"),
            mpf.make_addplot(pd.Series(70, index=df.index), panel=2, color="#ef535060", width=0.5, linestyle="--"),
            mpf.make_addplot(pd.Series(30, index=df.index), panel=2, color="#26a69a60", width=0.5, linestyle="--"),
        ]

        sig = result["signal"]
        if "BUY" in sig:
            m = pd.Series(float("nan"), index=df.index)
            m.iloc[-1] = float(df["Low"].iloc[-1]) * 0.98
            ap.append(mpf.make_addplot(m, type="scatter", marker="^", markersize=120, color="#26a69a"))
        elif "CLOSE" in sig:
            m = pd.Series(float("nan"), index=df.index)
            m.iloc[-1] = float(df["High"].iloc[-1]) * 1.02
            ap.append(mpf.make_addplot(m, type="scatter", marker="v", markersize=120, color="#ef5350"))

        fig, axes = mpf.plot(
            df, type="candle", style=style, addplot=ap, volume=True,
            panel_ratios=(3, 1, 1), figsize=(10, 7), returnfig=True, tight_layout=True,
        )

        name  = ticker.replace("KRW-", "")
        label = {"STRONG_BUY": "STRONG BUY", "BUY": "BUY",
                 "STRONG_CLOSE": "STRONG SELL", "CLOSE": "SELL"}.get(sig, sig)
        axes[0].set_title(
            f"{name}  {_fmt_krw(result['price'])}  ({result['daily_change']:+.1f}%)  |  "
            f"{label}  conf:{result['confidence']:.0f}",
            color="#ffffff", fontsize=13, fontweight="bold", loc="left", pad=10,
        )
        if "BUY" in sig:
            axes[0].axhline(y=result["stop_loss"],   color="#ef5350", lw=0.8, ls=":", alpha=0.7)
            axes[0].axhline(y=result["take_profit"], color="#26a69a", lw=0.8, ls=":", alpha=0.7)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                    facecolor="#1e1e2e", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"   ⚠️ {ticker} 차트 생성 실패: {e}")
        return None


# ============================================
# 메인
# ============================================
def main():
    now = utc_now()
    print(f"{'='*60}\n🪙 Coin Alert v1.0 — Upbit KRW 자동매매")
    print(f"   {now.strftime('%Y-%m-%d %H:%M:%S')} UTC | 자본: ₩{INITIAL_CAPITAL:,}")
    print(f"   비용: 수수료 {COMMISSION_BPS}bps + 슬리피지 {SLIPPAGE_BPS}bps = 편도 {TOTAL_COST_BPS}bps")
    print(f"   최대 노출: {MAX_PORTFOLIO_EXPOSURE*100:.0f}% | 종목당 상한: {MAX_POSITION_PCT*100:.0f}%")
    print(f"   리스크 예산: {RISK_BUDGET*100:.0f}%/거래 | 서킷브레이커: MDD {CIRCUIT_BREAKER_DD*100:.0f}%")
    print(f"   분석 {len(TICKERS)}종목: {', '.join(t.replace('KRW-', '') for t in TICKERS)}")
    print(f"   자동매매: {'✅ 활성' if AUTO_TRADE_ENABLED else '❌ 비활성 (알림만)'}")
    print(f"{'='*60}\n")

    # Phase 1: 데이터 & 분석
    fg = get_crypto_fear_greed()
    if fg:
        print(f"🧠 코인 공포탐욕: {fg['score']} ({fg['rating']})")

    print("📥 전 종목 데이터 조회 중...")
    signal_data, bt_data = fetch_all_data()

    # BTC 기반 레짐 감지
    btc_signal = signal_data.get("KRW-BTC")
    btc_bt     = bt_data.get("KRW-BTC")
    if btc_signal is not None and len(btc_signal) >= 200:
        regime_info = detect_market_regime(btc_signal)
    elif btc_bt is not None and len(btc_bt) >= 200:
        regime_info = detect_market_regime(btc_bt)
    else:
        regime_info = {"regime": "SIDEWAYS", "adx": 15, "vol_20": 50,
                       "above_sma50": True, "above_sma200": True}
    regime_weights = get_regime_strategy_weights(regime_info["regime"])
    threshold      = get_regime_threshold(regime_info["regime"])

    print(f"🌍 시장 레짐(BTC): {get_regime_emoji(regime_info['regime'])} "
          f"| ADX:{regime_info['adx']:.1f} | 변동성:{regime_info['vol_20']:.1f}% "
          f"| 임계값:{threshold}")

    # 포트폴리오 동기화
    portfolio = sync_portfolio_with_upbit(load_portfolio()) if AUTO_TRADE_ENABLED else load_portfolio()
    capital   = fetch_actual_capital()
    order_log = load_order_log()

    # 전 종목 분석
    print("\n📊 분석 시작...")
    results = []
    for ticker in TICKERS:
        sig_df = signal_data.get(ticker)
        bt_df  = bt_data.get(ticker)
        if sig_df is None:
            results.append({"ticker": ticker, "signal": "NO_DATA"})
            print(f"   ⚠️ {ticker}: 데이터 없음")
            continue
        r = analyze_ticker(
            ticker, sig_df, regime_info, regime_weights, fg,
            btc_data=btc_signal, backtest_data=bt_df,
        )
        results.append(r)
        name = ticker.replace("KRW-", "")
        print(f"   {name}: {r['signal']} (앙상블:{r['ensemble_score']:+.1f} 신뢰:{r['confidence']}/100 "
              f"RSI:{r['rsi']:.0f} ADX:{r['adx']:.0f})")
        print(f"      손절:{_fmt_krw(r['stop_loss'])} 익절:{_fmt_krw(r['take_profit'])} "
              f"Sharpe:{r['backtest']['sharpe']:.1f}")

    # Phase 2: 서킷브레이커
    cb_triggered, drawdown, peak_val = check_circuit_breaker(portfolio, capital, results)
    can_trade = AUTO_TRADE_ENABLED and not cb_triggered
    if cb_triggered:
        msg = (f"🚨 서킷브레이커 발동!\n"
               f"포트폴리오 MDD {drawdown*100:.1f}% ≥ {CIRCUIT_BREAKER_DD*100:.0f}%\n"
               f"고점 ₩{peak_val:,.0f} → 현재 ₩{portfolio.get('_meta', {}).get('last_value', 0):,.0f}\n"
               f"자동매매 일시 중단")
        print(f"\n🚨 {msg}")
        send_telegram(msg)

    # Phase 3: 매매 실행
    print("\n💹 매매 판단...")
    portfolio_tickers  = {k for k in portfolio if k != "_meta"}
    total_exposure     = sum(
        portfolio[t].get("volume", 0) * r["price"] / capital
        for r in results if r["signal"] != "NO_DATA"
        for t in [r["ticker"]] if t in portfolio
    )
    pending_buy_tickers = []
    pending_exposure   = 0.0
    signal_fired       = False

    for r in results:
        if r["signal"] == "NO_DATA":
            continue

        ticker = r["ticker"]

        # 트레일링 스탑 체크
        if ticker in portfolio and ticker != "_meta":
            current_hw = portfolio[ticker].get("high_watermark", portfolio[ticker]["entry_price"])
            if r["price"] > current_hw:
                portfolio[ticker]["high_watermark"] = r["price"]
                current_hw = r["price"]
            if r["atr"] > 0:
                new_stop   = current_hw - r["atr"] * ATR_STOP_MULT
                prev_stop  = portfolio[ticker].get("trailing_stop", 0)
                t_stop     = max(new_stop, prev_stop)
                portfolio[ticker]["trailing_stop"] = t_stop
                if r["price"] <= t_stop:
                    r["signal"] = "CLOSE"
                    r["close_reason"] = "TRAILING_STOP"
                    name = ticker.replace("KRW-", "")
                    print(f"   🛡️ {name} 트레일링 스탑: 고점{_fmt_krw(current_hw)} → 스탑{_fmt_krw(t_stop)}")

        # CLOSE 신호: 미보유 시 HOLD
        if r["signal"] in ["CLOSE", "STRONG_CLOSE"] and ticker not in portfolio:
            r["signal"] = "HOLD"

        ps = r["position"]

        # === 매수 ===
        if r["signal"] in ["BUY", "STRONG_BUY"]:
            if ticker in portfolio:
                name = ticker.replace("KRW-", "")
                print(f"   ℹ️ {name} 이미 보유 중 — 추가 매수 생략")
            else:
                corr_penalty    = calc_correlation_penalty(
                    list(portfolio_tickers) + pending_buy_tickers + [ticker],
                    {t: signal_data[t] for t in signal_data},
                )
                proposed_pct    = ps["position_pct"] / 100
                effective_exp   = (total_exposure + pending_exposure + proposed_pct) * corr_penalty
                name            = ticker.replace("KRW-", "")

                if effective_exp > MAX_PORTFOLIO_EXPOSURE:
                    print(f"   ⚠️ {name} 상관조정 노출 초과 ({effective_exp*100:.0f}% > {MAX_PORTFOLIO_EXPOSURE*100:.0f}%)")
                elif ps.get("method") == "BT_REJECT":
                    print(f"   ⚠️ {name} 백테스트 부적합 (Sharpe:{r['backtest'].get('sharpe', 0)}) — 매수 보류")
                elif ps.get("method") == "SKIP":
                    print(f"   ⚠️ {name} 신뢰도 부족 (conf:{r['confidence']:.0f}<40) — 매수 보류")
                elif ps["position_krw"] < 5000:
                    print(f"   ⚠️ {name} 투자금 부족 (₩{ps['position_krw']:,.0f} < 최소 ₩5,000)")
                else:
                    if can_trade:
                        if has_ordered_this_hour(order_log, ticker, "BUY"):
                            print(f"   ℹ️ {name} 금일 동시간대 이미 매수 주문 — 중복 방지")
                        else:
                            order = execute_buy(ticker, ps["position_krw"])
                            if order:
                                record_order(order_log, ticker, "BUY")
                                pending_exposure += proposed_pct
                                pending_buy_tickers.append(ticker)
                                signal_fired = True
                                send_telegram(
                                    f"📥 <b>{name}</b> 매수 주문 접수\n"
                                    f"{_fmt_krw(ps['position_krw'])} ({ps['position_pct']:.0f}%)\n"
                                    f"(체결 확인: 다음 sync)")
                                chart = generate_chart(ticker, signal_data.get(ticker, sig_df), r)
                                if chart:
                                    send_telegram_photo(chart, f"📥 {name} BUY {_fmt_krw(r['price'])}")
                            else:
                                send_telegram(f"❌ <b>{name}</b> 매수 주문 실패 — 수동 확인 필요")
                    else:
                        signal_fired = True
                        msg = format_signal_message(r)
                        if msg:
                            send_telegram(msg)
                        chart = generate_chart(ticker, signal_data.get(ticker, sig_df), r)
                        if chart:
                            send_telegram_photo(chart, msg[:1024] if msg else f"{name} BUY")
                        print(f"   📋 {name} 매수 신호 ({'장외 — 주문 미실행' if not cb_triggered else '서킷브레이커'})")

        # === 청산 ===
        elif r["signal"] in ["CLOSE", "STRONG_CLOSE"]:
            if ticker in portfolio:
                close_reason = r.get("close_reason", "SIGNAL")
                name         = ticker.replace("KRW-", "")
                vol          = portfolio[ticker].get("volume", 0)
                if can_trade:
                    if has_ordered_this_hour(order_log, ticker, "SELL"):
                        print(f"   ℹ️ {name} 동시간대 이미 매도 주문 — 중복 방지")
                    else:
                        order = execute_sell(ticker, vol)
                        if order:
                            record_order(order_log, ticker, "SELL")
                            signal_fired = True
                            entry_p = portfolio[ticker]["entry_price"]
                            pnl     = (r["price"] / entry_p - 1) * 100 if entry_p > 0 else 0
                            send_telegram(
                                f"📤 <b>{name}</b> 매도 주문 접수 ({close_reason})\n"
                                f"{vol} @ {_fmt_krw(r['price'])}\n"
                                f"진입{_fmt_krw(entry_p)} → 현재{_fmt_krw(r['price'])} ({pnl:+.1f}%)\n"
                                f"(체결 확인: 다음 sync)")
                            print(f"   🤖 매도 주문 접수 ({close_reason}): {_fmt_krw(r['price'])}")
                            chart = generate_chart(ticker, signal_data.get(ticker, sig_df), r)
                            if chart:
                                send_telegram_photo(chart, f"📤 {name} SELL {_fmt_krw(r['price'])}")
                        else:
                            send_telegram(f"❌ <b>{name}</b> 매도 주문 실패 — 수동 확인 필요")
                else:
                    signal_fired = True
                    msg = format_signal_message(r)
                    if msg:
                        send_telegram(msg)
                    chart = generate_chart(ticker, signal_data.get(ticker, sig_df), r)
                    if chart:
                        send_telegram_photo(chart, msg[:1024] if msg else f"{name} SELL")
                    print(f"   📋 {name} 청산 신호 ({close_reason}) ({'서킷브레이커' if cb_triggered else '알림만'})")

        # 특이사항 알림
        if r.get("volume_spike"):
            name = ticker.replace("KRW-", "")
            print(f"   🔊 {name} 거래량 급증 {r['volume_ratio']:.1f}x")
        if r.get("is_surge"):
            name = ticker.replace("KRW-", "")
            print(f"   ⚡ {name} 급{'등' if r['daily_change'] > 0 else '락'} {r['daily_change']:+.1f}%")

    save_portfolio(portfolio)

    # Phase 4: 리포트
    print(f"\n📁 포트폴리오 노출: {total_exposure*100:.1f}%")
    holdings = [k for k in portfolio if k != "_meta"]
    if holdings:
        print(f"   보유: {[t.replace('KRW-', '') for t in holdings]}")
    else:
        print("   보유 없음")

    if not signal_fired:
        status_msg = format_status_message(results, regime_info, fg)
        send_telegram(status_msg)

    print(f"\n✅ Coin Alert 완료: {utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)


if __name__ == "__main__":
    main()
