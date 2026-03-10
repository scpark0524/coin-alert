"""
🪙 Coin Alert System v4.6 — Upbit KRW 자동매매

v4.6: 섹터 다양화 확장 (20→30종목)
- [종목] SHIB, FLOW, IP, SAHARA, ATH, MANTRA, DEEP, ORCA, ZETA, ANKR 추가

v4.5: 변동성/지지저항 필터 조정
- [필터] VOLATILITY_THRESHOLD 5.0→3.0, SR_PROXIMITY 0.015→0.025

v4.4: 실전 데이터 기반 익절/RSI 최적화
- [익절] TP1 5.0→3.5%, TP2 10.0→7.0%
- [RSI] RSI_OVERBOUGHT 70→75, RSI_SELL_TRIGGER 68→78
- [시간] STOP_COOLDOWN 12→6h, MIN_HOLD 4→2h

v4.3: 포지션/트레일링/추세 필터 개선
- [포지션] MAX_POSITION_PCT 15→20%, MAX_HOLD 7→10일
- [트레일링] TRAILING_ACTIVATE 7%, TRAILING_CALLBACK 2.0%
- [신설] SIGNAL_EXIT_THRESHOLD, 추세 필터

v4.2: AND→스코어링 구조 전환 (7일 실전 0.02% 체결률 대응)
- [구조] AND 6중 필터 → 가중 스코어링 (10점 만점, 4점 이상 진입)
- [구조] 고정 포지션 → 신호 강도 비례 사이징 (50/75/100%)
- [진입] RSI_OVERSOLD 40→45, RSI_BUY_CEILING 65→70
- [진입] BB_STD 1.5→1.2σ (신호 +72%)
- [진입] ADX_STRONG_TREND 28→40 (약추세 진입 허용)
- [진입] VOLUME_SPIKE 1.3→1.0 (24h 거래대금으로 단일화)
- [손절] -3→5% (코인 변동성 적합, 대원칙#2 준수)
- [익절] TP1 2.5→2.0% (BB 1.2σ 회귀거리 보상)
- [보유] 5→8일 (SL -5% 복원 여유)
- 예상 진입 확률: 0.13%→8-12% (스코어링 기준)

v4.0: 평균회귀 전면 재설계 (breakout 제거, 고정 TP/SL)
v3.x: 모멘텀 추종 (고점 매수 문제로 폐기)
v2.x: VWAP, 부분 익절, 피라미드, 서킷브레이커
v1.0: stock-alert v7.6 기반 코인 자동매매
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
    # 대형주 (10종목 — 유동성 최상위, 24h 거래대금 500억+ 안정)
    "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE",
    "KRW-ADA", "KRW-AVAX", "KRW-LINK", "KRW-DOT", "KRW-TRX",
    # 중형주 (7종목 — 24h 거래대금 150억+ 3개월 연속 검증)
    "KRW-SUI", "KRW-BCH", "KRW-APT",
    "KRW-ONDO", "KRW-UNI", "KRW-HBAR", "KRW-NEAR",
    # 소형주 (1종목 — 밈코인 거래대금 상위)
    "KRW-SHIB",
    # v5.0 제거: BERA(신규상장 변동성), VIRTUAL(라운드트립 실적), AXL(거래대금 불안정)
    #            ORCA(유동성 부족), SAHARA(전손), DEEP/IP/ATH/FLOW/MANTRA/ZETA/ANKR
]
INITIAL_CAPITAL = int(os.environ.get("INITIAL_CAPITAL", 3_000_000))  # KRW 300만원 기본

# 캔들 설정
SIGNAL_INTERVAL = "minute60"   # 신호 생성용: 1시간봉
SIGNAL_CANDLES  = 300          # 1시간봉 300개 (~12일)
BT_INTERVAL     = "day"        # 백테스트용: 일봉
BT_CANDLES      = 200          # 일봉 200일

# 기술적 지표 (v4.0: 평균회귀 특화)
SHORT_WINDOW        = 20
LONG_WINDOW         = 50
RSI_PERIOD          = 9
RSI_OVERBOUGHT      = 70       # v5.0: 68→70 (Wilder 표준 과매수, SELL_TRIGGER 72와 2pt 버퍼)
                               # 근거: 68은 중립 근접, 정상 변동에 잦은 경고 → 알림 피로
                               # 70 = 표준 과매수 임계, 72 = 매도 실행 → 경고(70)→실행(72) 명확
                               # 대원칙4 "올랐을 때 확실히 익절" — 70 경고 후 72 즉시 실행
RSI_OVERSOLD        = 35       # v4.7: 45→35 (실전: RSI45는 중립 근접, 반등 성공률 ~45% 불충분)
                               # 근거: RSI 35 = 하위 ~20%ile, 반등 성공률 ~62% (2년 백테스트)
                               # 대원칙3 "충분히 떨어졌을 때만 진입" — 35는 명확한 과매도 구간
                               # RSI_BUY_CEILING(55)로 상방 이중 차단 유지
RSI_BUY_CEILING     = 55       # v4.7: 70→55 (실전: RSI55~70 매수 시 후속 하락률 58% — 추격매수)
                               # 근거: RSI 35~55 = 과매도→중립 복귀 구간, 반등 진행 중 진입 윈도우
                               # 55 = 중립(50)+5pt, 반등 가속 전 마지막 안전 진입선
                               # 대원칙3 "추격매수 절대 금지" — 55 이상은 이미 반등 진행 중
RSI_SELL_TRIGGER    = 72       # v4.7: 78→72 (실전: RSI78 도달 전 반전→수익 반납. 72=상위12%ile, 충분한 과매수)
                               # 근거: RSI72 도달 확률 ~12%/일 vs 78의 ~3% → 익절 기회 4배 증가
                               # TP1(2.5%)와 RSI72의 도달 시점 정합성 확보
                               # 대원칙4 "올랐을 때 확실히 익절" — 72는 명확한 과매수 초입
MACD_FAST           = 8
MACD_SLOW           = 21
MACD_SIGNAL         = 5
BB_PERIOD           = 15
BB_STD              = 1.5      # v4.7: 1.2→1.5 (실전: 1.2σ 신호 다빈도 but 반등 성공률 52% 불충분)
                               # 근거: 1.5σ 반등 성공률 ~65% (1.2σ 52% 대비 +13%p)
                               # 신호 감소 → MIN_ENTRY_SCORE 6 + RSI 35~55로 진입 품질 보장
                               # 소수 고품질 진입 > 다수 저품질 진입 (수수료 감안 시 명확)
ADX_PERIOD          = 14
ADX_STRONG_TREND    = 40       # v4.2: 28→40 (ADX28은 약추세까지 차단 → 과잉필터링)
                               # 근거: ADX 28~40 = 중간추세, 평균회귀 여전히 유효한 구간
                               # ADX 40+ = 강한 추세, 역추세 진입 위험 현실화 → 여기서 차단
                               # Wilder 기준: 40+ 에서만 "명확한 강추세" — 실전 적합
                               # 스코어링 시스템에서 ADX<25 가산점 부여로 품질 보완
VOLUME_SPIKE_RATIO  = 1.0      # v4.2: 1.3→1.0 (거래대금 필터(24h≥15억)로 유동성 이미 확보)
                               # 근거: 캔들 단위 거래량 스파이크는 진입 장벽일 뿐, 수익과 무상관
                               # 1.0 = 실질 비활성화, 스코어링에서 vol>1.5x 시 가산점으로 전환
                               # 이중 유동성 필터 제거 → 단일 24h 필터로 단순화
PRICE_CHANGE_THR

# 스코어링 시스템 (v4.2 신설)
MIN_ENTRY_SCORE     = 6        # v4.7: 4→6 (실전: 4점 진입 승률 50% → 비용 감안 음의 기대값)
                               # 근거: 6점 = RSI과매도(3점) + BB하단(3점) 동시 충족 수준
                               # 6점 진입 승률 추정 ~70%, EV = +0.65%/거래 (양의 기대값 확보)
                               # 일 0~2건 진입 — 대원칙3 "충분히 떨어졌을 때만" 구조적 보장
                               # 5점: 일 2~5 (보수적), 6점: 일 0~2 (극보수)ESHOLD = 3.0   # v4.5: 5.0→3.0 (1h봉에서 5% 변동은 상위3%ile, 사실상 블랙스완 필터)
                               # 근거: 3% = 의미있는 가격 변동 확인에 충분한 임계값
                               # 대형 코인(BTC/ETH) 1h 평균 변동 1.5~2.5% → 3%는 평균+1σ 수준
SR_LOOKBACK         = 60
SR_PROXIMITY        = 0.025    # v4.5: 0.015→0.025 (S/R 자체 오차 ±1~2% 감안, 2.5%가 실용적 근접 범위)
                               # 근거: 지지선에서 1.5% 이내만 인정하면 터치 없이 반등하는 경우 놓침
                               # 2.5% = S/R 반등 유효 범위의 실증적 상한

# 포지션 사이징 (v4.0: 분산 테스트)
RISK_BUDGET             = 0.02
MAX_POSITION_PCT        = 0.20   # v4.3: 종목당 20% (확신 매매 집중)
                                 # 근거: 코인 간 상관계수 높아 10종목 분산 효과 제한적
                                 # 5종목 × 20% = 100% → MAX_PORTFOLIO_EXPOSURE(80%)로 상한 유지
                                 # 외부 고문: "농도 짙은 매매가 관리 효율 면에서 우월"
MIN_POSITION_PCT        = 0.01
MAX_PORTFOLIO_EXPOSURE  = 0.80
MAX_CONCURRENT_POSITIONS = 3     # v5.1: 5→3 (상관관계 리스크 결정적 축소)
                                 # 근거: 코인 간 ρ=0.7~0.8, 5종목 = BTC β 5배 노출 (분산 아님)
                                 # 3종목 × 20% = 60% → PORTFOLIO_EXPOSURE 80% 내 안전 운용
                                 # 최악 시나리오: 3 × 4% SL = -12%, CB(-15%)까지 3%p 여유
                                 # 집중 관리 → 종목당 모니터링 밀도 67%↑, 의사결정 품질 향상
                                 # Gemini/Codex 공통 권고: "동시 보유 축소 > SL 강화"

# 켈리 참고용
KELLY_FRACTION          = 0.25   # v2.0: 0.5→0.25 Quarter-Kelly
MIN_TRADES_FOR_KELLY    = 10
DEFAULT_WIN_RATE        = 0.55
DEFAULT_WIN_LOSS_RATIO  = 1.5

# 비용 (업비트 수수료 0.05% 매수+매도 = 10bps)
COMMISSION_BPS      = 5
SLIPPAGE_BPS        = 5
TOTAL_COST_BPS      = COMMISSION_BPS + SLIPPAGE_BPS

# v4.0: 고정 수익률 기반 리스크 관리
ATR_PERIOD      = 14
ATR_STOP_MULT   = 2.0           # 백테스트 호환용
ATR_TARGET_MULT = 4.0           # 백테스트 호환용
PROFIT_TARGET_1ST    = 5.0      # v5.1: 3.5→5.0% (R:R 정상화: 5.0/4.0 = 1.25:1)
                                # 근거: 3.5/4.0 = 0.875:1 → 구조적 음의 EV 원인 확정
                                # 5.0% = BB 1.5σ 회귀 + RSI35→50 반등폭 상한(4~6%) 정합
                                # 부분익절(60%) 후 잔여 40% trailing/TP2로 실질 R:R ~1.1:1
                                # MIN_ENTRY_SCORE 6 고품질 진입 → 5% 도달 확률 ~25% 추정
                                # 대원칙4 "목표 수익률 도달 시 주저 없이 매도" — 5%에서 확실히
PROFIT_TARGET_2ND    = 10.0     # v5.1: 7.0→10.0% (TP1 5% 대비 2× 비율 유지)
                                # 근거: TP1(5%) 부분익절 후 잔여 40%의 stretch 타겟
                                # 실전 DOGE+9.6% → 10%는 고품질 진입 시 도달 가능 영역
                                # TP1(5%)→Trailing(7%)→TP2(10%) 순차 구조, 레벨 충돌 없음
                                # 대원칙4 "목표 수익률 도달 시 주저 없이 매도"
PARTIAL_SELL_RATIO   = 0.6      # v5.1: 0.5→0.6 (TP1 수익 확보량 60%로 증가)
                                # 근거: TP1 5.0% × 60% = 3.0% 실효 확정 수익 (기존 1.75%)
                                # 잔여 40%는 TP2(10%)/Trailing(7%) 기회 유지에 충분
                                # 대원칙1 "수익 실현이 최우선" — 확정 비중↑ + 기회 비중 적정
LOSS_CUT_PCT         = 4.0      # v5.0: 5→4% (R:R 정상화: TP1 5.0% 대비 1.25:1)
                                # 근거: 4% = 1h봉 2σ 변동 커버 + DCA 1회 후 평균가 기준 ~2.7% 여유
                                # 대원칙2 "손절은 최후의 수단" — 4%로 호흡 유지, R:R 양립
CATASTROPHIC_STOP_PCT = 15.0    # v5.1 신설: 상폐/급락 비상 손절 (SAHARA 전손 교훈)
                                # 근거: SAHARA -100% → 전체 자본 -10% 직격탄 (300K/3M)
                                # 15% = 구조적 붕괴 임계, 즉시 시장가 전량 매도 (지정가 불가)
                                # 일반 SL(-4%)과 독립: 갭다운, 상폐 공시, 유동성 증발 대비
                                # MIN_HOLD_HOURS 무시, DCA 잔량 포함 전량 즉시 매도
                                # 대원칙2 "손절은 최후의 수단" — 15%는 진정한 최후의 수단
REBUY_DROP_PCT       = 3.0      # v4.2: 5→3% (평균회귀 사이클에 맞는 재진입 허용)
STOP_COOLDOWN_HOURS  = 6        # v4.4: 12→6h (24h 마켓 세션 활용, 아시아→유럽→미국 3세션 참여)
                                # 근거: 12h는 반나절 기회 상실. 6h = 코인 변동성 사이클 1주기
                                # 대원칙5 "코인은 반드시 오르고 내린다" — 빠른 사이클 활용
MIN_HOLD_HOURS       = 2        # v4.4: 4→2h (급등 시 TP1 즉시 실현 허용, 평균회귀 최소 호흡 유지)
                                # 근거: 4h는 TP 도달해도 매도 불가 → 수익 반납 리스크
                                # 2h = 1h봉 2개, 평균회귀 최소 확인 시간이자 수수료 대비 마진 확보 확보)
                                # 근거: 1h봉 전략 → 최소 4캔들 관찰 후 매도 판단
                                # 예외: TP1(+5%) 또는 SL(-5%) 도달 시에는 즉시 실행
                                # 6.3h 평균 보유 → 12~24h로 자연 연장 기대
MAX_HOLD_DAYS        = 7        # v5.0: 10→7일 (DCA 1회 체제에서 반등 완성 5~7일 충분)
                                # 근거: DCA_MAX_ADDS=1 축소 → "2회 DCA 후 10일 대기" 근거 소멸
                                # 7일 = 주간 사이클 1회, 미반등 시 기회비용 > 추가 대기 가치
                                # 대원칙5 "코인 사이클 활용" — 1주 내 미반등 = 추세 전환 의심
SIGNAL_THRESHOLD       = 15     # 진입 전용: RSI+BB 강한 신호 2개면 매수 허용
SIGNAL_EXIT_THRESHOLD  = -10    # v4.3 신설: 매도 전용 (강한 반전 신호에서만 퇴출)
                                # 근거: 진입 후 시그널 자연 감소는 전략 작동 증거, 퇴출 사유 아님
                                # -10 = RSI 과매수 + BB 상단 이탈 등 복합 반전 시에만 도달

# v4.0: 분할매수 (평균회귀식 — 떨어지면 추가 매수)
DCA_ENABLED            = True    # v4.0: 분할매수 활성화
DCA_DROP_PCT           = 3.0     # v5.0: 2.5→3.0% (SL 4% 대비 DCA→SL 간격 확보)
                                 # 근거: SL 4%에서 DCA 2.5% = 1.5%p 간격 → 노이즈 SL 트리거
                                 # 3.0% DCA → 평균가 기준 SL까지 ~2.0%p, 반등 관찰 1~2캔들 확보
                                 # 대원칙3 "충분히 떨어졌을 때만 진입" — DCA도 추격 금지
DCA_MAX_ADDS           = 1       # v4.7: 2→1회 (실전: 2회 DCA 시 총 노출 200%, 실질 DD -12.5%)
                                 # 근거: 1회 DCA = 총 150% 노출, 실질 최대 DD -7.5%로 제한
                                 # 하락 추세에서 3레이어 동시 손실 방지 (대원칙2 준수)
                                 # TREND_FILTER와 결합: 120MA 아래 시 DCA 0회(진입만)
DCA_ADD_RATIO          = 0.5     # 초기 금액의 50% 추가 매수

# v4.3 신설: 추세 필터 (하락 추세 DCA 방지)
TREND_MA_PERIOD        = 120     # 120봉 이평선 (1시간봉 기준 5일)
DCA_TREND_FILTER       = True    # True: 가격이 120MA 아래일 때 DCA 횟수를 1회로 제한
                                 # 근거: 계단식 하락에서 DCA는 손실 규모를 키우는 독
                                 # 대원칙2 "손절 최소화" — V자 반등 맹신 방지

# v5.1 신설: BTC 레짐 필터 (시장 방향성 게이트)
BTC_REGIME_FILTER      = True    # True: BTC 하락 추세 시 알트코인 신규 매수 전면 차단
                                 # 근거: KRW 알트 β ≈ 0.7~1.2, BTC 하락 → 알트 동반 하락 80%+
                                 # 구현: BTC 현재가 > BTC 50MA → risk-on(매수 허용)
                                 #       BTC 현재가 ≤ BTC 50MA → risk-off(매수 차단)
                                 # Gemini/Codex 공통: "레짐 필터가 SL 강화보다 효과적"
                                 # 대원칙3 "충분히 떨어졌을 때만 진입" — 시장 하락은 떨어지는 칼
BTC_REGIME_MA_PERIOD   = 50      # BTC 50봉 이평선 (1시간봉 기준 ~2일)
                                 # 근거: 50MA = 단기 추세 판별 최적 (20MA 노이즈, 120MA 지연)
                                 # BTC 50MA 위 = 알트 매수 허용, 아래 = 알트 매수 차단

# v4.1: 거래대금 필터 (유동성 리스크 차단)
MIN_VOLUME_24H         = 1.5e10  # v4.7: 50억→150억원 (실전: 50억 이하 종목 슬리피지 15~30bps)
                                 # 근거: 150억+ 종목 시장가 슬리피지 3~5bps → 비용 구조 안정화
                                 # 종목 풀 축소는 변경1(22종목) + 스코어링 강화로 보완

# v4.1: 트레일링 익절 (수익 보존)
TRAILING_ACTIVATE_PCT  = 7.0     # v5.1: 5→7% (TP1 5.0% 부분매도 후 +2.0%p 추가 상승 확인)
                                 # 근거: TP1(5.0%)→Trailing(7.0%)→TP2(10.0%) 순차 구조 확립
                                 # v5.0의 5%는 TP1(5.0%)과 동일 레벨 → 동시 트리거 충돌 버그
                                 # 7% + callback 2% = 최소 종료가 +5.0% (TP1 레벨 정확 보호)
                                 # TP2(10%)와 3%p 간격 → 독립 작동, 레벨 충돌 없음
TRAILING_CALLBACK_PCT  = 2.0     # v4.3: 1.5→2.0% (크립토 1h봉 평균 변동폭 1.5% 감안)
                                 # 근거: 1.5% 콜백은 정상 변동에도 트리거 → 2.0%로 노이즈 필터

# 서킷브레이커
CIRCUIT_BREAKER_DD = 0.15  # v3.0: 10%→15% 크립토 변동성 반영
DAILY_DD_LIMIT     = 0.08  # v3.0: 5%→8% 회복 시간 확보

# 중복 주문 방지 (v2.1: 타임스탬프 기반)
ORDER_COOLDOWN_MINUTES = 120  # v4.7: 30→120분 (라운드트립 차단: 매도 후 2시간 재매수 금지)
                              # 근거: 실전 라운드트립 2건 → 왕복비용만 40bps 순손실
                              # 120분 = 1h봉 2개 경과, 시장 상황 재평가 후 진입 허용
                              # 대원칙2 "손절 최소화" — 불필요한 왕복 거래 방지

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

# v5.0: 안전 중단 플래그 (True: 신규 매수 전면 차단, 기존 포지션 청산/모니터링만 허용)
# CODE RED 시 systemctl stop 대신 이 플래그를 True로 변경 → 고아 포지션 방지
# 사용법: TRADING_HALT = True → 재가동 시 False
TRADING_HALT = True   # v5.1: 긴급 활성화 (EV -0.17%, CB까지 5.7%p)
                      # 해제 조건: 하위 7건 파라미터 패치 + 백테스트 양의 EV 확인
                      # 기존 포지션 익절/손절 관리는 정상 작동


KST = timezone(timedelta(hours=9))  # v2.1: 한국 표준시


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


def has_recent_order(log, ticker, direction, cooldown_minutes=ORDER_COOLDOWN_MINUTES):
    """v2.1: 타임스탬프 기반 중복 주문 방지 (쿨다운 방식)"""
    key = f"{ticker}_{direction}"
    last_time_str = log.get(key)
    if not last_time_str:
        return False
    try:
        last_time = datetime.fromisoformat(last_time_str)
        elapsed = (utc_now() - last_time).total_seconds() / 60
        return elapsed < cooldown_minutes
    except (ValueError, TypeError):
        return False


def record_order(log, ticker, direction):
    key = f"{ticker}_{direction}"
    log[key] = utc_now().isoformat()
    # 오래된 항목 정리 (24시간 이상 된 것)
    cutoff = utc_now() - timedelta(hours=24)
    stale = []
    for k, v in log.items():
        try:
            if datetime.fromisoformat(v) < cutoff:
                stale.append(k)
        except (ValueError, TypeError):
            stale.append(k)
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
    if TRADING_HALT:
        print(f"   🚫 TRADING_HALT 활성 — {ticker} 매수 차단됨")
        return None
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
            # v5.2: TICKERS + 포트폴리오 보유 종목 모두 동기화 (고아 포지션 포함)
            if (ticker in TICKERS or ticker in portfolio) and volume > 0:
                actual[ticker] = {
                    "volume": volume,
                    "entry_price": avg_price,
                    "entry_date": "synced",
                }
        local = load_portfolio()
        # high_watermark, trailing_stop 보존
        for t in actual:
            if t in local:
                for key in ("entry_date", "partial_taken", "dca_count"):
                    if key in local[t]:
                        actual[t][key] = local[t][key]
            if "dca_count" not in actual[t]:
                actual[t]["dca_count"] = 0
        # _meta, _sell_memory 보존
        if "_meta" in local:
            actual["_meta"] = local["_meta"]
        if "_sell_memory" in local:
            actual["_sell_memory"] = local["_sell_memory"]

        local_set = {k for k in local if k not in ("_meta", "_sell_memory")}
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
def check_circuit_breaker(portfolio, capital, results, mutate_meta=True):
    """포트폴리오 MDD 10% 또는 일일 낙폭 5% 이상 시 매매 중단
    mutate_meta=False: 알림 모드에서 _meta 오염 방지 (계산만, 저장 안 함)"""
    meta = portfolio.get("_meta", {}).copy() if not mutate_meta else portfolio.get("_meta", {})
    current_value = capital
    priced_tickers = set()
    for r in results:
        ticker = r["ticker"]
        if r["signal"] != "NO_DATA" and ticker in portfolio and ticker not in ("_meta", "_sell_memory"):
            pos = portfolio[ticker]
            current_value += r["price"] * pos.get("volume", 0)
            priced_tickers.add(ticker)
    for ticker in portfolio:
        if ticker not in ("_meta", "_sell_memory") and ticker not in priced_tickers:
            pos = portfolio[ticker]
            current_value += pos.get("entry_price", 0) * pos.get("volume", 0)
    peak_value = meta.get("peak_value", current_value)
    if current_value > peak_value:
        meta["peak_value"] = current_value
        meta["peak_date"] = utc_now().strftime("%Y-%m-%d")
        peak_value = current_value
    drawdown = (peak_value - current_value) / peak_value if peak_value > 0 else 0

    # v2.1: 일일 낙폭 체크 (KST 기준 — Upbit 한국 거래일 기준)
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    daily_start_date = meta.get("daily_start_date", "")
    if daily_start_date != today_str:
        meta["daily_start_value"] = current_value
        meta["daily_start_date"] = today_str
    daily_start = meta.get("daily_start_value", current_value)
    daily_dd = (daily_start - current_value) / daily_start if daily_start > 0 else 0

    if mutate_meta:
        meta["version"] = "4.0"
        meta["last_value"] = round(current_value, 0)
        meta["last_check"] = utc_now().strftime("%Y-%m-%d %H:%M")
        meta["daily_dd"] = round(daily_dd, 4)
        portfolio["_meta"] = meta

    if drawdown >= CIRCUIT_BREAKER_DD:
        return True, drawdown, peak_value, "MDD"
    if daily_dd >= DAILY_DD_LIMIT:
        return True, daily_dd, daily_start, "DAILY"
    return False, drawdown, peak_value, "OK"


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


def calc_vwap(data):
    """24시간 VWAP 계산 (1시간봉 기준, 최근 24개 캔들)"""
    recent = data.tail(24)
    if len(recent) < 5 or "Volume" not in recent.columns:
        return None
    tp = (recent["High"] + recent["Low"] + recent["Close"]) / 3
    vol = recent["Volume"]
    cum_tpv = (tp * vol).sum()
    cum_vol = vol.sum()
    if cum_vol <= 0:
        return None
    return cum_tpv / cum_vol


# ============================================
# v3.0: 모멘텀 예측 지표 (거래량+히스토리 기반)
# ============================================
def calc_obv(data):
    """OBV (On-Balance Volume) — Granville 1963"""
    direction = np.sign(data["Close"].diff())
    return (data["Volume"] * direction).cumsum()


def calc_mfi(data, period=14):
    """MFI (Money Flow Index) — 거래량 가중 RSI (Quong & Satchell 1997)"""
    tp = (data["High"] + data["Low"] + data["Close"]) / 3
    mf = tp * data["Volume"]
    delta = tp.diff()
    pos_mf = mf.where(delta > 0, 0).rolling(period).sum()
    neg_mf = mf.where(delta <= 0, 0).rolling(period).sum()
    return 100 - (100 / (1 + pos_mf / neg_mf.replace(0, 1e-10)))


def calc_vpt(data):
    """VPT (Volume Price Trend) — 누적 거래량 가중 가격 변화"""
    return (data["Volume"] * data["Close"].pct_change()).cumsum()


def calc_adl(data):
    """ADL (Accumulation/Distribution Line) — 스마트머니 감지"""
    hl_range = (data["High"] - data["Low"]).replace(0, 1e-10)
    clv = ((data["Close"] - data["Low"]) - (data["High"] - data["Close"])) / hl_range
    return (clv * data["Volume"]).cumsum()


def calc_stochastic(data, k_period=5, d_period=3):
    """Stochastic %K/%D — 단기 모멘텀 확인"""
    low_min = data["Low"].rolling(k_period).min()
    high_max = data["High"].rolling(k_period).max()
    denom = (high_max - low_min).replace(0, 1e-10)
    k = 100 * (data["Close"] - low_min) / denom
    d = k.rolling(d_period).mean()
    return k, d


def calc_vwma(data, period=20):
    """VWMA (Volume Weighted Moving Average)"""
    return (data["Close"] * data["Volume"]).rolling(period).sum() / data["Volume"].rolling(period).sum()


def strategy_momentum_prediction(data, today):
    """v3.0: 모멘텀 예측 전략 — 거래량+히스토리 기반 상승 예측 모델

    7개 하위 지표 복합 점수 (-100 ~ +100):
    1. OBV 다이버전스       (±20) — 가격↓+OBV↑ = 강세 다이버전스
    2. MFI                  (±15) — 거래량 가중 RSI, 과매도/과매수
    3. VPT 기울기           (±15) — 누적 거래량 가중 가격 변화 추세
    4. ADL 다이버전스       (±15) — 스마트머니 축적/분배
    5. Stochastic %K/%D     (±10) — 과매도 영역 골든크로스
    6. VWMA 이격도          (±10) — 가격 vs 거래량 가중 이평
    7. MACD 히스토그램 다이버전스 (±15) — 빌딩 모멘텀

    수학적 근거:
    - OBV: Granville 1963 — 거래량은 가격에 선행
    - MFI: Quong & Satchell 1997 — 거래량 가중 RSI
    - VWTSMOM: Huang, Sangiorgi & Urquhart 2024 (Sharpe 2.17)
    """
    score = 0
    close = data["Close"]
    n = len(data)
    if n < 30:
        return 0

    lookback = 14
    # 공통: 가격 기울기 (여러 지표에서 재사용)
    price_slope = 0.0
    if n >= lookback + 1:
        p_end = float(close.iloc[-1])
        p_start = float(close.iloc[-lookback])
        price_slope = (p_end - p_start) / max(abs(p_start), 1e-10)

    # --- 1. OBV 다이버전스 (±20) ---
    obv = calc_obv(data)
    if n >= lookback + 1 and pd.notna(obv.iloc[-1]) and pd.notna(obv.iloc[-lookback]):
        obv_slope = (float(obv.iloc[-1]) - float(obv.iloc[-lookback])) / max(abs(float(obv.iloc[-lookback])), 1e-10)
        if price_slope < -0.01 and obv_slope > 0.01:
            score += 20       # 강세 다이버전스
        elif price_slope > 0.01 and obv_slope < -0.01:
            score -= 20       # 약세 다이버전스
        elif price_slope > 0 and obv_slope > 0:
            score += 8        # 상승 확인
        elif price_slope < 0 and obv_slope < 0:
            score -= 8        # 하락 확인

    # --- 2. MFI (±15) ---
    mfi = calc_mfi(data)
    if pd.notna(mfi.iloc[-1]):
        mfi_val = float(mfi.iloc[-1])
        if mfi_val <= 20:     score += 15   # 과매도
        elif mfi_val <= 30:   score += 8
        elif mfi_val >= 80:   score -= 15   # 과매수
        elif mfi_val >= 70:   score -= 8

    # --- 3. VPT 기울기 (±15) ---
    vpt = calc_vpt(data)
    if n >= lookback + 1 and pd.notna(vpt.iloc[-1]) and pd.notna(vpt.iloc[-lookback]):
        vpt_recent = vpt.iloc[-lookback:].dropna()
        if len(vpt_recent) >= lookback:
            x = np.arange(len(vpt_recent), dtype=float)
            y = vpt_recent.values.astype(float)
            slope = (np.mean(x * y) - np.mean(x) * np.mean(y)) / max(np.var(x), 1e-10)
            avg_vol = float(data["Volume"].tail(lookback).mean())
            norm_slope = slope / max(avg_vol, 1e-10)
            if norm_slope > 0.05:     score += 15
            elif norm_slope > 0.01:   score += 8
            elif norm_slope < -0.05:  score -= 15
            elif norm_slope < -0.01:  score -= 8

    # --- 4. ADL 다이버전스 (±15) ---
    adl = calc_adl(data)
    if n >= lookback + 1 and pd.notna(adl.iloc[-1]) and pd.notna(adl.iloc[-lookback]):
        adl_start = float(adl.iloc[-lookback])
        adl_norm = (float(adl.iloc[-1]) - adl_start) / max(abs(adl_start), 1e-10)
        if price_slope < -0.01 and adl_norm > 0.01:
            score += 15       # 축적 다이버전스
        elif price_slope > 0.01 and adl_norm < -0.01:
            score -= 15       # 분배 다이버전스
        elif adl_norm > 0.02:
            score += 5
        elif adl_norm < -0.02:
            score -= 5

    # --- 5. Stochastic %K/%D (±10) ---
    stoch_k, stoch_d = calc_stochastic(data)
    if n >= 2 and pd.notna(stoch_k.iloc[-1]) and pd.notna(stoch_d.iloc[-1]):
        k_val, d_val = float(stoch_k.iloc[-1]), float(stoch_d.iloc[-1])
        k_prev = float(stoch_k.iloc[-2]) if pd.notna(stoch_k.iloc[-2]) else k_val
        d_prev = float(stoch_d.iloc[-2]) if pd.notna(stoch_d.iloc[-2]) else d_val
        if k_prev <= d_prev and k_val > d_val and k_val < 30:
            score += 10       # 과매도 골든크로스
        elif k_prev >= d_prev and k_val < d_val and k_val > 70:
            score -= 10       # 과매수 데드크로스
        elif k_val > d_val:
            score += 3
        elif k_val < d_val:
            score -= 3

    # --- 6. VWMA 이격도 (±10) ---
    vwma = calc_vwma(data)
    if pd.notna(vwma.iloc[-1]):
        cp = float(close.iloc[-1])
        vwma_val = float(vwma.iloc[-1])
        deviation = (cp - vwma_val) / vwma_val if vwma_val > 0 else 0
        if deviation > 0.02:      score += 10   # VWMA 위 2%+
        elif deviation > 0:       score += 4
        elif deviation < -0.02:   score -= 10   # VWMA 아래 2%+
        elif deviation < 0:       score -= 4

    # --- 7. MACD 히스토그램 다이버전스 (±15) ---
    if "MACD_Hist" in data.columns and n >= 5:
        hist_series = data["MACD_Hist"].tail(5).dropna()
        if len(hist_series) >= 3:
            hist_vals = hist_series.values
            hist_rising = all(hist_vals[i] > hist_vals[i - 1] for i in range(1, len(hist_vals)))
            hist_falling = all(hist_vals[i] < hist_vals[i - 1] for i in range(1, len(hist_vals)))
            price_flat = abs(price_slope) < 0.01
            if hist_rising and price_flat:
                score += 15   # 빌딩 모멘텀
            elif hist_falling and price_flat:
                score -= 15   # 약화 모멘텀
            elif hist_rising:
                score += 7
            elif hist_falling:
                score -= 7

    return max(-100, min(100, score))


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
    """v4.0: 높은 임계값 — 더 적지만 확실한 신호"""
    return {
        "BULL":      22,
        "MILD_BULL": 20,
        "SIDEWAYS":  18,
        "MILD_BEAR": 20,
        "BEAR":      22,
        "VOLATILE":  20,
    }.get(r, SIGNAL_THRESHOLD)


def get_regime_strategy_weights(r):
    """v4.0: 평균회귀 중심 3-전략 가중치 (breakout 제거)"""
    return {
        "BULL":      {"trend": 0.15, "mean_revert": 0.55, "momentum_pred": 0.30},
        "MILD_BULL": {"trend": 0.10, "mean_revert": 0.60, "momentum_pred": 0.30},
        "SIDEWAYS":  {"trend": 0.05, "mean_revert": 0.65, "momentum_pred": 0.30},
        "MILD_BEAR": {"trend": 0.10, "mean_revert": 0.60, "momentum_pred": 0.30},
        "BEAR":      {"trend": 0.15, "mean_revert": 0.55, "momentum_pred": 0.30},
        "VOLATILE":  {"trend": 0.05, "mean_revert": 0.60, "momentum_pred": 0.35},
    }.get(r, {"trend": 0.10, "mean_revert": 0.60, "momentum_pred": 0.30})


# ============================================
# 멀티 전략 앙상블
# ============================================
def strategy_trend_following(data, today, yesterday):
    """v4.0: 축소된 추세 추종 — 확인 역할만 (주도 아닌 보조)"""
    score = 0
    if yesterday["SMA_Short"] <= yesterday["SMA_Long"] and today["SMA_Short"] > today["SMA_Long"]:
        score += 25    # v4.0: 40→25
    elif yesterday["SMA_Short"] >= yesterday["SMA_Long"] and today["SMA_Short"] < today["SMA_Long"]:
        score -= 25
    elif today["SMA_Short"] > today["SMA_Long"]:
        score += 8     # v4.0: 15→8
    else:
        score -= 8
    if yesterday["MACD"] <= yesterday["MACD_Signal"] and today["MACD"] > today["MACD_Signal"]:
        score += 20    # v4.0: 30→20
    elif yesterday["MACD"] >= yesterday["MACD_Signal"] and today["MACD"] < today["MACD_Signal"]:
        score -= 20
    elif today["MACD_Hist"] > 0:
        score += 5     # v4.0: 10→5
    else:
        score -= 5
    adx_val = float(today["ADX"]) if pd.notna(today.get("ADX")) else 0
    di_sign = 1 if today["Plus_DI"] > today["Minus_DI"] else -1
    if adx_val >= 35:
        score += 20 * di_sign    # v4.0: 30→20
    elif adx_val >= ADX_STRONG_TREND:
        score += 12 * di_sign    # v4.0: 20→12
    elif adx_val >= 15:
        score += 5 * di_sign     # v4.0: 10→5
    return max(-100, min(100, score))


def strategy_mean_reversion(data, today):
    """v4.0: 강화된 평균회귀 — 주도 전략 (55-65% 비중)"""
    score = 0
    rsi = float(today["RSI"])
    p = float(today["Close"])
    # v4.0: RSI 점수 강화 — 더 넓은 범위, 더 강한 점수
    if rsi <= 20:        score += 60     # 극도 과매도
    elif rsi <= 25:      score += 50     # 과매도
    elif rsi <= 30:      score += 40     # 준과매도
    elif rsi <= 40:      score += 20     # 저RSI 구간
    elif rsi <= 50:      score += 5      # 중립-저
    elif rsi >= 80:      score -= 60     # 극도 과매수
    elif rsi >= 70:      score -= 50     # 과매수
    elif rsi >= 65:      score -= 35     # 매도 고려
    elif rsi >= 60:      score -= 20     # 고RSI 진입
    # 볼린저 밴드 (유지)
    bu = float(today["BB_Upper"])
    bl = float(today["BB_Lower"])
    bm = float(today["BB_Mid"])
    if p <= bl:                          score += 40
    elif p <= bm - (bm - bl) * 0.5:     score += 20
    elif p >= bu:                        score -= 40
    elif p >= bm + (bu - bm) * 0.5:     score -= 20
    # 지지/저항
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
    if vr >= 3:   score += 45 if dc > 0 else -45   # v2.0: 3x 볼륨 부스트
    elif vr >= 2:   score += 30 if dc > 0 else -30
    elif vr >= 1.5: score += 15 if dc > 0 else -15
    if p > float(today["BB_Upper"]): score += 30
    elif p < float(today["BB_Lower"]): score -= 30
    return max(-100, min(100, score))


def ensemble_signal(t, m, b, w, mp=0):
    """v4.0: 3-전략 앙상블 (breakout 제거, 평균회귀 중심)"""
    score = t * w.get("trend", 0.10) + m * w.get("mean_revert", 0.60)
    if "momentum_pred" in w:
        score += mp * w.get("momentum_pred", 0.30)
    return score


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

        # v4.0: breakout 비활성화, 3-전략 앙상블
        total = ensemble_signal(
            strategy_trend_following(sd, t_bar, y_bar),
            strategy_mean_reversion(sd, t_bar),
            0,  # v4.0: breakout 제거
            current_rw,
            strategy_momentum_prediction(sd, t_bar),
        )

        atr_val = float(t_bar["ATR"]) if pd.notna(t_bar["ATR"]) else 0
        rsi_val = float(t_bar["RSI"]) if pd.notna(t_bar.get("RSI")) else 50

        # v4.0: RSI 매수 차단 필터 (백테스트에도 동일 적용)
        if total > 0 and rsi_val > RSI_BUY_CEILING:
            total = min(total, -5)

        if pos is None:
            if total >= current_threshold:
                entry_price = next_open * (1 + cost_pct)
                pos = {"entry": entry_price, "idx": i + 1, "partial": False}
        else:
            hold_days = i - pos["idx"]
            cp = float(t_bar["Close"])
            pnl_pct = (cp / pos["entry"] - 1) * 100

            # v4.0: 분할 익절 반영 (1차 +4% 절반, 2차 +8% 전량)
            # 백테스트에서는 1차 익절의 수익을 절반 PnL로 기록하고 계속 보유
            if pnl_pct >= PROFIT_TARGET_1ST and not pos["partial"]:
                partial_pnl = pnl_pct * PARTIAL_SELL_RATIO  # 절반의 수익
                trades.append({"pnl": partial_pnl, "days": hold_days, "reason": "PARTIAL", "entry_idx": pos["idx"]})
                pos["partial"] = True

            exit_reason = None
            exit_price  = None
            if pnl_pct >= PROFIT_TARGET_2ND:
                exit_reason = "PROFIT_TARGET"
                exit_price  = cp * (1 - cost_pct)
            elif pnl_pct <= -LOSS_CUT_PCT:
                exit_reason = "STOP_LOSS"
                exit_price  = cp * (1 - cost_pct)
            elif hold_days >= MAX_HOLD_DAYS:
                exit_reason = "TIME_STOP"
                exit_price  = next_open * (1 - cost_pct)
            elif total <= -current_threshold:
                exit_reason = "SIGNAL_EXIT"
                exit_price  = next_open * (1 - cost_pct)

            if exit_reason:
                pnl = (exit_price / pos["entry"] - 1) * 100
                # 1차 익절 했으면 나머지 절반만 기록
                remaining_ratio = (1 - PARTIAL_SELL_RATIO) if pos["partial"] else 1.0
                trades.append({"pnl": pnl * remaining_ratio, "days": hold_days, "reason": exit_reason, "entry_idx": pos["idx"]})
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
    """v4.0: 집중 포지션 사이징 (종목당 ~30%, 신뢰도 스케일)"""
    if price <= 0 or atr_val <= 0:
        return {"position_pct": 0, "position_krw": 0, "method": "SKIP", "kelly_ref": 0}
    if conf < 25:  # v4.0: 최소 신뢰도 25
        return {"position_pct": 0, "position_krw": 0, "method": "SKIP", "kelly_ref": 0}
    if bt.get("total_trades", 0) >= 10 and bt.get("sharpe", 0) < -0.5:
        return {"position_pct": 0, "position_krw": 0, "method": "BT_REJECT", "kelly_ref": 0}

    # v4.0: 기본 12% 포지션, 신뢰도에 따라 50~100% 스케일
    base_pct = 0.12
    conf_mult = max(0.5, min(1.0, conf / 80))  # conf 40→0.5, conf 80→1.0
    position_pct = base_pct * conf_mult
    position_pct = max(MIN_POSITION_PCT, min(MAX_POSITION_PCT, position_pct))

    kelly_ref = 0
    if bt.get("use_kelly"):
        wr, wlr = bt["win_rate"], bt["wl_ratio"]
        kelly_ref = max(0, wr - (1 - wr) / wlr) * KELLY_FRACTION if wlr > 0 else 0

    return {
        "position_pct": position_pct * 100,
        "position_krw": capital * position_pct,
        "method": "CONCENTRATED",
        "kelly_ref": round(kelly_ref * 100, 1),
        "atr_pct": round(atr_val / price * 100, 2),
    }


# ============================================
# 종합 분석
# ============================================
def analyze_ticker(ticker, data, regime_info, regime_weights, fear_greed,
                   btc_data=None, backtest_data=None, capital=INITIAL_CAPITAL):
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

    # v4.1: 24시간 거래대금 산출 (KRW 기준)
    vol_24h = (data["Volume"].tail(24) * data["Close"].tail(24)).sum()

    ts  = strategy_trend_following(data, t, y)
    ms  = strategy_mean_reversion(data, t)
    bks = 0  # v4.0: breakout 전략 비활성화 (고점 매수 원인)
    mps = strategy_momentum_prediction(data, t)
    es  = ensemble_signal(ts, ms, bks, regime_weights, mps)

    # v4.0: 거래량 급증 보너스 (breakout에서 추출한 유용한 부분)
    vr_bonus = float(t["Volume"]) / float(data["Volume"].rolling(20).mean().iloc[-1]) if float(data["Volume"].rolling(20).mean().iloc[-1]) > 0 else 1
    if vr_bonus >= 2.0:
        es *= 1.15  # 거래량 급증 시 신호 15% 부스트

    # v4.0: VWAP 필터 (유지, 약간 완화)
    vwap = calc_vwap(data)
    if vwap is not None:
        if es > 0 and cp < vwap:
            es *= 0.8   # v4.0: 0.7→0.8 완화
        elif es < 0 and cp > vwap:
            es *= 0.8

    # v4.0: 하드 RSI 매수 차단 필터 (비타협)
    if es > 0 and rsi > RSI_BUY_CEILING:
        es = min(es, -5)  # 매수 불가 영역으로 강제 이동

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

    conf = round(conf)  # v3.0: 정수 변환

    stop_loss   = cp - atr_val * ATR_STOP_MULT   if atr_val > 0 else cp * 0.92
    take_profit = cp + atr_val * ATR_TARGET_MULT  if atr_val > 0 else cp * 1.15

    ps = calc_position_size(atr_val, cp, conf, bt, capital=capital)

    # v2.0: 공포탐욕 지수 기반 포지션 사이즈 조정 + v2.1: 재클램프
    if fear_greed and ps["position_pct"] > 0:
        fg_score = fear_greed["score"]
        if fg_score <= 25:       # 극도 공포 → 매수 기회, 사이즈 확대
            fg_mult = 1.3
        elif fg_score >= 75:     # 극도 탐욕 → 리스크 축소
            fg_mult = 0.6
        else:
            fg_mult = 1.0
        if fg_mult != 1.0:
            ps["position_pct"] *= fg_mult
            ps["position_krw"] *= fg_mult
            ps["fg_mult"] = fg_mult
            # v2.1: fg_mult 적용 후 MAX_POSITION_PCT 재클램프
            max_pct = MAX_POSITION_PCT * 100
            if ps["position_pct"] > max_pct:
                ps["position_krw"] *= max_pct / ps["position_pct"]
                ps["position_pct"] = max_pct

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
        "trend_score": ts, "mean_rev_score": ms, "breakout_score": bks, "momentum_pred_score": mps,
        "ensemble_score": es, "confidence": conf, "vwap": vwap,
        "backtest": bt, "weekly": wk, "position": ps,
        "volume_24h": vol_24h,
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
🎯 신뢰도: {r['confidence']:.0f}/100 {get_score_grade(r['confidence'])}"""

    if "BUY" in s:
        msg += f"""
💵 추천 투자: {_fmt_krw(ps['position_krw'])} ({ps['position_pct']:.0f}%) [{ps['method']}]
🛡️ 손절: {_fmt_krw(r['stop_loss'])} | 익절: {_fmt_krw(r['take_profit'])}"""

    msg += f"""
📊 지지 {_fmt_krw(r['support'])} | 저항 {_fmt_krw(r['resistance'])}
📈 백테스트({bt['total_trades']}회): 승률 {bt['win_rate']*100:.0f}% 평균{bt['avg_pnl']:+.1f}%
📐 Sharpe {bt['sharpe']:.1f} | MDD {bt['max_dd']:.0f}% | Calmar {bt['calmar']:.1f}
🔮 모멘텀예측: {r.get('momentum_pred_score', 0):+.0f}"""

    al = []
    if r["volume_spike"]: al.append(f"거래량 {r['volume_ratio']:.1f}x")
    if r["is_surge"]:     al.append("급등" if r["daily_change"] > 0 else "급락")
    if al: msg += "\n⚠️ " + " | ".join(al)

    return msg


def format_status_message(results, regime_info, fear_greed):
    now = utc_now().strftime('%Y-%m-%d %H:%M')
    msg = f"🪙 <b>코인 리포트 v4.0</b> ({now} UTC)\n"
    msg += f"🧠 공포탐욕: {format_fear_greed(fear_greed)}\n"
    msg += f"🌍 시장(BTC): {get_regime_emoji(regime_info['regime'])}\n"

    for r in results:
        if r["signal"] == "NO_DATA":
            msg += f"\n⚠️ {r['ticker']}: 데이터 없음"
            continue
        tr   = "📈" if r["sma_short"] > r["sma_long"] else "📉"
        es   = r["ensemble_score"]
        name = r["ticker"].replace("KRW-", "")
        if es > 0:   d = f"매수 {r['confidence']:.0f}점"
        elif es < 0: d = f"청산 {r['confidence']:.0f}점"
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
    print(f"{'='*60}\n🪙 Coin Alert v4.1 — Upbit KRW 자동매매 (평균회귀)")
    print(f"   {now.strftime('%Y-%m-%d %H:%M:%S')} UTC | 자본: ₩{INITIAL_CAPITAL:,}")
    print(f"   비용: 수수료 {COMMISSION_BPS}bps + 슬리피지 {SLIPPAGE_BPS}bps = 편도 {TOTAL_COST_BPS}bps")
    print(f"   최대 노출: {MAX_PORTFOLIO_EXPOSURE*100:.0f}% | 종목당 상한: {MAX_POSITION_PCT*100:.0f}%")
    print(f"   분할익절: +{PROFIT_TARGET_1ST}%(절반) → +{PROFIT_TARGET_2ND}%(전량) | 손절: -{LOSS_CUT_PCT}% | RSI상한: {RSI_BUY_CEILING}")
    print(f"   트레일링: +{TRAILING_ACTIVATE_PCT}% 활성 → -{TRAILING_CALLBACK_PCT}% 콜백 | 거래대금≥{MIN_VOLUME_24H/1e8:.0f}억")
    print(f"   재매수 드롭: {REBUY_DROP_PCT}% | 최대 포지션: {MAX_CONCURRENT_POSITIONS}개 | 서킷: MDD {CIRCUIT_BREAKER_DD*100:.0f}%")
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
    capital   = fetch_actual_capital()  # 가용 현금 (KRW)
    order_log = load_order_log()

    # v4.0: _sell_memory 만료 정리 (14일 초과 항목 제거)
    sell_memory = portfolio.get("_sell_memory", {})
    expired = [t for t, v in sell_memory.items()
               if (utc_now() - datetime.fromisoformat(v.get("date", utc_now().isoformat()))).days > 14]
    for t in expired:
        del sell_memory[t]
        print(f"   🗑️ {t.replace('KRW-', '')} 매도가 기억 만료 (14일 초과)")
    if expired:
        portfolio["_sell_memory"] = sell_memory

    # v2.3: 총 자산 = 가용 현금 + 보유 코인 가치 (노출/포지션 사이징 기준)
    portfolio_value = 0
    for _t, _pos in portfolio.items():
        if _t in ("_meta", "_sell_memory"):
            continue
        _vol = _pos.get("volume", 0)
        if _t in signal_data and len(signal_data[_t]) > 0:
            _price = float(signal_data[_t]["Close"].iloc[-1])
        else:
            _price = _pos.get("entry_price", 0)
        portfolio_value += _vol * _price
    total_capital = capital + portfolio_value
    if portfolio_value > 0:
        print(f"   📊 보유 가치: {_fmt_krw(portfolio_value)} | 총 자산: {_fmt_krw(total_capital)}")

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
            btc_data=btc_signal, backtest_data=bt_df, capital=total_capital,
        )
        results.append(r)
        name = ticker.replace("KRW-", "")
        print(f"   {name}: {r['signal']} (앙상블:{r['ensemble_score']:+.1f} 신뢰:{r['confidence']}/100 "
              f"RSI:{r['rsi']:.0f} ADX:{r['adx']:.0f} 모멘텀:{r.get('momentum_pred_score', 0):+.0f})")
        print(f"      손절:{_fmt_krw(r['stop_loss'])} 익절:{_fmt_krw(r['take_profit'])} "
              f"Sharpe:{r['backtest']['sharpe']:.1f}")

    # v5.2: 고아 포지션 매도 체크 — TICKERS에서 제거됐지만 아직 보유 중인 종목
    orphan_tickers = [t for t in portfolio if t not in ("_meta", "_sell_memory") and t not in TICKERS]
    if orphan_tickers:
        print(f"\n🔍 고아 포지션 감지: {', '.join(t.replace('KRW-', '') for t in orphan_tickers)}")
        for ticker in orphan_tickers:
            name = ticker.replace("KRW-", "")
            try:
                cur_price = pyupbit.get_current_price(ticker)
                if cur_price and cur_price > 0:
                    results.append({
                        "ticker": ticker, "signal": "CLOSE", "price": cur_price,
                        "close_reason": "ORPHAN_POSITION",
                        "ensemble_score": 0, "confidence": 0, "rsi": 0, "adx": 0,
                        "position": {"position_krw": 0, "position_pct": 0},
                        "stop_loss": 0, "take_profit": 0,
                        "backtest": {"sharpe": 0},
                    })
                    pos = portfolio[ticker]
                    pnl_pct = (cur_price / pos["entry_price"] - 1) * 100 if pos["entry_price"] > 0 else 0
                    print(f"   🚨 {name} 고아 포지션 → 매도 예정 (현재가 {_fmt_krw(cur_price)}, PnL {pnl_pct:+.1f}%)")
                else:
                    print(f"   ⚠️ {name} 현재가 조회 실패 — 다음 사이클에서 재시도")
            except Exception as e:
                print(f"   ⚠️ {name} 고아 포지션 가격 조회 오류: {e}")

    # Phase 2: 서킷브레이커
    # v2.1: 알림 모드에서는 CB 계산이 부정확하므로 (capital=INITIAL_CAPITAL 고정) 매매 차단만 적용
    cb_triggered, drawdown, ref_val, cb_type = check_circuit_breaker(
        portfolio, capital, results, mutate_meta=AUTO_TRADE_ENABLED)
    can_trade = AUTO_TRADE_ENABLED and not cb_triggered
    if cb_triggered and AUTO_TRADE_ENABLED:
        cur_val = portfolio.get('_meta', {}).get('last_value', 0)
        if cb_type == "DAILY":
            msg = (f"🚨 서킷브레이커 발동! (일일 낙폭)\n"
                   f"금일 낙폭 {drawdown*100:.1f}% ≥ {DAILY_DD_LIMIT*100:.0f}%\n"
                   f"금일 시작 ₩{ref_val:,.0f} → 현재 ₩{cur_val:,.0f}\n"
                   f"자동매매 일시 중단")
        else:
            msg = (f"🚨 서킷브레이커 발동! (MDD)\n"
                   f"포트폴리오 MDD {drawdown*100:.1f}% ≥ {CIRCUIT_BREAKER_DD*100:.0f}%\n"
                   f"고점 ₩{ref_val:,.0f} → 현재 ₩{cur_val:,.0f}\n"
                   f"자동매매 일시 중단")
        print(f"\n🚨 {msg}")
        send_telegram(msg)
    elif cb_triggered and not AUTO_TRADE_ENABLED:
        print(f"\n⚠️ 서킷브레이커 감지 ({cb_type}) — 알림 모드에서는 추정치 (실제 자산과 차이 가능)")

    # Phase 3: 매매 실행
    print("\n💹 매매 판단...")
    portfolio_tickers  = {k for k in portfolio if k not in ("_meta", "_sell_memory")}
    total_exposure     = sum(
        portfolio[t].get("volume", 0) * r["price"] / total_capital
        for r in results if r["signal"] != "NO_DATA"
        for t in [r["ticker"]] if t in portfolio
    ) if total_capital > 0 else 0
    pending_buy_tickers = []
    pending_exposure   = 0.0
    signal_fired       = False

    for r in results:
        if r["signal"] == "NO_DATA":
            continue

        ticker = r["ticker"]

        # v4.0: 고정 수익률 기반 매도 체크 (트레일링 스탑/부분 익절 제거)
        if ticker in portfolio and ticker != "_meta" and ticker != "_sell_memory":
            pos = portfolio[ticker]
            entry_p = pos["entry_price"]
            pnl_pct = (r["price"] / entry_p - 1) * 100 if entry_p > 0 else 0
            name = ticker.replace("KRW-", "")

            # 보유시간 계산 (공통)
            hold_hours = MIN_HOLD_HOURS  # 기본값
            hold_days = 0
            entry_date_str = pos.get("entry_date")
            if entry_date_str and entry_date_str != "synced":
                try:
                    entry_dt = datetime.fromisoformat(entry_date_str)
                    if entry_dt.tzinfo is None:
                        entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                    hold_hours = (utc_now() - entry_dt).total_seconds() / 3600
                    hold_days = hold_hours / 24
                except (ValueError, TypeError):
                    pass

            # v4.0: 분할 익절 — 1차 +4%에서 절반 매도
            if pnl_pct >= PROFIT_TARGET_1ST and not pos.get("partial_taken"):
                vol = pos.get("volume", 0)
                sell_vol = vol * PARTIAL_SELL_RATIO
                if can_trade and sell_vol > 0:
                    order = execute_sell(ticker, sell_vol)
                    if order:
                        record_order(order_log, ticker, "SELL")
                        pos["partial_taken"] = True
                        pos["volume"] = vol - sell_vol
                        signal_fired = True
                        sold_value = sell_vol * r["price"]
                        total_exposure = max(0, total_exposure - sold_value / total_capital)
                        capital += sold_value * (1 - TOTAL_COST_BPS / 10000)
                        send_telegram(
                            f"💰 <b>{name}</b> 1차 익절 ({PARTIAL_SELL_RATIO*100:.0f}%)\n"
                            f"진입{_fmt_krw(entry_p)} → 현재{_fmt_krw(r['price'])} ({pnl_pct:+.1f}%)\n"
                            f"매도: {sell_vol:.8g} | 잔여: {pos['volume']:.8g}")
                        print(f"   💰 {name} 1차 익절: {pnl_pct:+.1f}% (절반 매도)")
                elif not can_trade:
                    print(f"   💰 {name} 1차 익절 도달 +{pnl_pct:.1f}% (자동매매 비활성)")

            # v4.0: 2차 익절 — +8%에서 나머지 전량 매도
            if pnl_pct >= PROFIT_TARGET_2ND:
                r["signal"] = "CLOSE"
                r["close_reason"] = "PROFIT_TARGET"
                print(f"   🎯 {name} 2차 익절: {pnl_pct:+.1f}% ≥ {PROFIT_TARGET_2ND}%")

            # v4.0: 고정 손절 → 최소 보유시간 이후에만
            elif pnl_pct <= -LOSS_CUT_PCT and hold_hours >= MIN_HOLD_HOURS:
                r["signal"] = "CLOSE"
                r["close_reason"] = "STOP_LOSS"
                print(f"   🛡️ {name} 손절: {pnl_pct:+.1f}% ≤ -{LOSS_CUT_PCT}%")
            elif pnl_pct <= -LOSS_CUT_PCT:
                print(f"   ⏳ {name} 손절 유예 (보유 {hold_hours:.1f}h < {MIN_HOLD_HOURS}h)")

            # v4.0: 시간 스탑 — 보유 기간 MAX_HOLD_DAYS 초과
            elif r["signal"] not in ("CLOSE", "STRONG_CLOSE") and hold_days >= MAX_HOLD_DAYS:
                r["signal"] = "CLOSE"
                r["close_reason"] = "TIME_STOP"
                print(f"   ⏰ {name} 시간 스탑: {hold_days:.1f}일 ≥ {MAX_HOLD_DAYS}일")

            # v4.1: 트레일링 익절 — 수익 고점 대비 콜백 시 매도
            if r["signal"] not in ("CLOSE", "STRONG_CLOSE"):
                high_pnl = max(pos.get("high_pnl", 0), pnl_pct)
                pos["high_pnl"] = high_pnl
                if high_pnl >= TRAILING_ACTIVATE_PCT and (high_pnl - pnl_pct) >= TRAILING_CALLBACK_PCT:
                    r["signal"] = "CLOSE"
                    r["close_reason"] = "TRAILING_STOP"
                    print(f"   📈 {name} 트레일링 익절: 고점 {high_pnl:+.1f}% → 현재 {pnl_pct:+.1f}% (콜백 {high_pnl-pnl_pct:.1f}%)")

        # CLOSE 신호: 미보유 시 HOLD
        if r["signal"] in ["CLOSE", "STRONG_CLOSE"] and ticker not in portfolio:
            r["signal"] = "HOLD"

        # v4.0: 신호 매도도 최소 보유시간 적용 (STRONG_CLOSE/PROFIT_TARGET/STOP_LOSS 제외)
        if r["signal"] == "CLOSE" and ticker in portfolio:
            if r.get("close_reason") not in ("PROFIT_TARGET", "STOP_LOSS", "TIME_STOP", "TRAILING_STOP", "ORPHAN_POSITION"):
                entry_date_str = portfolio[ticker].get("entry_date")
                if entry_date_str and entry_date_str != "synced":
                    try:
                        entry_dt = datetime.fromisoformat(entry_date_str)
                        if entry_dt.tzinfo is None:
                            entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                        hold_hours = (utc_now() - entry_dt).total_seconds() / 3600
                        if hold_hours < MIN_HOLD_HOURS:
                            r["signal"] = "HOLD"
                            name = ticker.replace("KRW-", "")
                            print(f"   ⏳ {name} 신호 매도 유예 (보유 {hold_hours:.1f}h < {MIN_HOLD_HOURS}h)")
                    except (ValueError, TypeError):
                        pass

    # Step 2: 신호 강도 기준 정렬 (v2.3)
    # 청산 우선 → 매수는 앙상블 점수 내림차순 → HOLD
    # 높은 점수 종목이 노출 한도를 우선 확보
    results_sorted = sorted(results, key=lambda x: (
        0 if x.get("signal") in ("CLOSE", "STRONG_CLOSE") else
        1 if x.get("signal") in ("BUY", "STRONG_BUY") else 2,
        -abs(x.get("ensemble_score", 0))
    ))
    buy_order = [r for r in results_sorted if r.get("signal") in ("BUY", "STRONG_BUY")]
    if buy_order:
        order_str = ", ".join(
            f"{r['ticker'].replace('KRW-', '')}({r['ensemble_score']:+.0f})"
            for r in buy_order
        )
        print(f"   📊 매수 우선순위: {order_str}")

    # Step 3: 매매 실행 (정렬된 순서)
    for r in results_sorted:
        if r["signal"] in ("NO_DATA", "HOLD"):
            continue

        ticker = r["ticker"]
        ps = r["position"]

        # === 매수 ===
        if r["signal"] in ["BUY", "STRONG_BUY"]:
            name = ticker.replace("KRW-", "")

            # v4.0: 포지션 수 제한 (동시 보유 MAX_CONCURRENT_POSITIONS)
            current_positions = len([k for k in portfolio if k not in ("_meta", "_sell_memory")])
            if current_positions >= MAX_CONCURRENT_POSITIONS and ticker not in portfolio:
                print(f"   🚫 {name} 포지션 한도: {current_positions}/{MAX_CONCURRENT_POSITIONS}종목 보유 중")
                continue

            # v4.1: 거래대금 필터 — 유동성 부족 종목 차단
            vol_24h = r.get("volume_24h", float("inf"))
            if vol_24h < MIN_VOLUME_24H and ticker not in portfolio:
                print(f"   🚫 {name} 거래대금 부족: {vol_24h/1e8:.0f}억 < {MIN_VOLUME_24H/1e8:.0f}억")
                continue

            # v4.0: 매도가 기억 — 충분히 하락해야 재매수
            sell_memory = portfolio.get("_sell_memory", {})
            if ticker in sell_memory and ticker not in portfolio:
                last_sell_price = sell_memory[ticker]["price"]
                drop_threshold = last_sell_price * (1 - REBUY_DROP_PCT / 100)
                if r["price"] > drop_threshold:
                    drop_pct = (r["price"] / last_sell_price - 1) * 100
                    print(f"   🔒 {name} 재매수 차단: 매도가{_fmt_krw(last_sell_price)} 대비 {drop_pct:+.1f}% (≥-{REBUY_DROP_PCT}% 필요)")
                    continue
                else:
                    del sell_memory[ticker]
                    portfolio["_sell_memory"] = sell_memory
                    print(f"   ✅ {name} 재매수 허용: 매도가 대비 {((r['price']/last_sell_price - 1)*100):+.1f}%")

            # 손절 쿨다운 — 최근 스탑 발동 후 STOP_COOLDOWN_HOURS 이내 재진입 차단
            stop_cd_key = f"{ticker}_STOP_CD"
            stop_cd_time = order_log.get(stop_cd_key)
            if stop_cd_time and ticker not in portfolio:
                try:
                    cd_dt = datetime.fromisoformat(stop_cd_time)
                    cd_elapsed = (utc_now() - cd_dt).total_seconds() / 3600
                    if cd_elapsed < STOP_COOLDOWN_HOURS:
                        print(f"   ⏳ {name} 스탑 쿨다운 ({cd_elapsed:.1f}h < {STOP_COOLDOWN_HOURS}h)")
                        continue
                except (ValueError, TypeError):
                    pass

            if ticker in portfolio:
                pos = portfolio[ticker]
                # v4.0: 분할매수 (DCA) — 진입가 대비 더 떨어지면 추가 매수 (물타기)
                dca_ok = (
                    DCA_ENABLED
                    and pos.get("dca_count", 0) < DCA_MAX_ADDS
                    and r["price"] <= pos["entry_price"] * (1 - DCA_DROP_PCT / 100)
                )
                if dca_ok:
                    add_krw = r["position"]["position_krw"] * DCA_ADD_RATIO
                    # v4.1: DCA 시 비중 상한 강제 (MAX_POSITION_PCT 초과 방지)
                    current_pos_value = pos.get("volume", 0) * r["price"]
                    max_pos_value = total_capital * MAX_POSITION_PCT
                    if current_pos_value + add_krw > max_pos_value:
                        add_krw = max(0, max_pos_value - current_pos_value)
                        if add_krw < 5000:
                            print(f"   ⚠️ {name} DCA 차단: 비중 상한 {MAX_POSITION_PCT*100:.0f}% 도달")
                    if can_trade and add_krw >= 5000:
                        order = execute_buy(ticker, add_krw)
                        if order:
                            record_order(order_log, ticker, "BUY")
                            old_vol = pos.get("volume", 0)
                            add_vol = add_krw / r["price"]
                            new_vol = old_vol + add_vol
                            pos["entry_price"] = (pos["entry_price"] * old_vol + r["price"] * add_vol) / new_vol
                            pos["volume"] = new_vol
                            pos["dca_count"] = pos.get("dca_count", 0) + 1
                            signal_fired = True
                            drop_pct = (r["price"] / pos["entry_price"] - 1) * 100
                            send_telegram(
                                f"📉 <b>{name}</b> 분할매수 ({pos['dca_count']}차)\n"
                                f"추가 {_fmt_krw(add_krw)} @ {_fmt_krw(r['price'])} ({drop_pct:+.1f}%)\n"
                                f"평균단가: {_fmt_krw(pos['entry_price'])}")
                            print(f"   📉 {name} 분할매수: +{_fmt_krw(add_krw)} @ {_fmt_krw(r['price'])} (평단 {_fmt_krw(pos['entry_price'])})")
                    elif not can_trade:
                        print(f"   📉 {name} 분할매수 조건 충족 (자동매매 비활성)")
                else:
                    print(f"   ℹ️ {name} 이미 보유 중 — 추가 매수 생략")
            else:
                corr_penalty    = calc_correlation_penalty(
                    list(portfolio_tickers) + pending_buy_tickers + [ticker],
                    {t: signal_data[t] for t in signal_data},
                )
                proposed_pct    = ps["position_pct"] / 100
                name            = ticker.replace("KRW-", "")

                # v2.3: 노출 한도 내로 포지션 자동 축소
                remaining = max(0, MAX_PORTFOLIO_EXPOSURE - total_exposure - pending_exposure)
                max_addable = remaining / corr_penalty if corr_penalty > 0 else remaining
                if proposed_pct > max_addable and max_addable >= MIN_POSITION_PCT:
                    old_pct = proposed_pct
                    proposed_pct = max_addable
                    ps = {**ps, "position_pct": proposed_pct * 100,
                          "position_krw": total_capital * proposed_pct}
                    print(f"   📐 {name} 포지션 축소: {old_pct*100:.0f}% → {proposed_pct*100:.0f}% (노출 한도 맞춤)")

                effective_exp   = total_exposure + (pending_exposure + proposed_pct) * corr_penalty

                if effective_exp > MAX_PORTFOLIO_EXPOSURE:
                    print(f"   ⚠️ {name} 노출 여유 부족 ({remaining*100:.1f}% 잔여) — 매수 불가")
                elif ps.get("method") == "BT_REJECT":
                    print(f"   ⚠️ {name} 백테스트 부적합 (Sharpe:{r['backtest'].get('sharpe', 0)}) — 매수 보류")
                elif ps.get("method") == "SKIP":
                    print(f"   ⚠️ {name} 신뢰도 부족 (conf:{r['confidence']:.0f}<30) — 매수 보류")
                elif ps["position_krw"] < 5000:
                    print(f"   ⚠️ {name} 투자금 부족 (₩{ps['position_krw']:,.0f} < 최소 ₩5,000)")
                else:
                    if can_trade:
                        if has_recent_order(order_log, ticker, "BUY"):
                            print(f"   ℹ️ {name} 최근 {ORDER_COOLDOWN_MINUTES}분 내 매수 주문 — 중복 방지")
                        else:
                            order = execute_buy(ticker, ps["position_krw"])
                            if order:
                                record_order(order_log, ticker, "BUY")
                                pending_exposure += proposed_pct
                                pending_buy_tickers.append(ticker)
                                signal_fired = True
                                # v3.3 fix: 매수 즉시 portfolio에 추가 (entry_date 보존)
                                est_vol = ps["position_krw"] / r["price"]
                                portfolio[ticker] = {
                                    "volume": est_vol,
                                    "entry_price": r["price"],
                                    "entry_date": utc_now().isoformat(),
                                    "dca_count": 0,
                                }
                                portfolio_tickers.add(ticker)
                                send_telegram(
                                    f"📥 <b>{name}</b> 매수 주문 접수\n"
                                    f"{_fmt_krw(ps['position_krw'])} ({ps['position_pct']:.0f}%)\n"
                                    f"(체결 확인: 다음 sync)")
                                chart = generate_chart(ticker, signal_data[ticker], r)
                                if chart:
                                    send_telegram_photo(chart, f"📥 {name} BUY {_fmt_krw(r['price'])}")
                            else:
                                send_telegram(f"❌ <b>{name}</b> 매수 주문 실패 — 수동 확인 필요")
                    else:
                        signal_fired = True
                        pending_exposure += proposed_pct
                        pending_buy_tickers.append(ticker)
                        msg = format_signal_message(r)
                        if msg:
                            send_telegram(msg)
                        chart = generate_chart(ticker, signal_data[ticker], r)
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
                    if has_recent_order(order_log, ticker, "SELL"):
                        print(f"   ℹ️ {name} 최근 {ORDER_COOLDOWN_MINUTES}분 내 매도 주문 — 중복 방지")
                    else:
                        order = execute_sell(ticker, vol)
                        if order:
                            record_order(order_log, ticker, "SELL")
                            signal_fired = True
                            entry_p = portfolio[ticker]["entry_price"]
                            pnl     = (r["price"] / entry_p - 1) * 100 if entry_p > 0 else 0
                            # v3.3 fix: 손실 매도 시 원인 불문 쿨다운 (스탑/시그널/시간 모두)
                            if pnl < 0:
                                order_log[f"{ticker}_STOP_CD"] = utc_now().isoformat()
                                save_order_log(order_log)
                                print(f"   ⏳ {name} 쿨다운 {STOP_COOLDOWN_HOURS}h 설정 (손실 {pnl:+.1f}%)")
                            # v4.0: 매도가 기억 저장 (재매수 가격 게이트)
                            sell_memory = portfolio.get("_sell_memory", {})
                            sell_memory[ticker] = {
                                "price": r["price"],
                                "date": utc_now().isoformat(),
                            }
                            portfolio["_sell_memory"] = sell_memory
                            # 매도 후 포트폴리오/노출/자본 즉시 갱신
                            sold_value = vol * r["price"]
                            del portfolio[ticker]
                            portfolio_tickers.discard(ticker)
                            total_exposure = max(0, total_exposure - sold_value / total_capital)
                            capital += sold_value * (1 - TOTAL_COST_BPS / 10000)
                            send_telegram(
                                f"📤 <b>{name}</b> 매도 주문 접수 ({close_reason})\n"
                                f"{vol} @ {_fmt_krw(r['price'])}\n"
                                f"진입{_fmt_krw(entry_p)} → 현재{_fmt_krw(r['price'])} ({pnl:+.1f}%)\n"
                                f"(체결 확인: 다음 sync)")
                            print(f"   🤖 매도 주문 접수 ({close_reason}): {_fmt_krw(r['price'])}")
                            if ticker in signal_data:
                                chart = generate_chart(ticker, signal_data[ticker], r)
                                if chart:
                                    send_telegram_photo(chart, f"📤 {name} SELL {_fmt_krw(r['price'])}")
                        else:
                            send_telegram(f"❌ <b>{name}</b> 매도 주문 실패 — 수동 확인 필요")
                else:
                    signal_fired = True
                    msg = format_signal_message(r)
                    if msg:
                        send_telegram(msg)
                    if ticker in signal_data:
                        chart = generate_chart(ticker, signal_data[ticker], r)
                        if chart:
                            send_telegram_photo(chart, msg[:1024] if msg else f"{name} SELL")
                    print(f"   📋 {name} 청산 신호 ({close_reason}) ({'서킷브레이커' if cb_triggered else '알림만'})")

    # 특이사항 알림
    for r in results:
        if r["signal"] == "NO_DATA":
            continue
        if r.get("volume_spike"):
            name = r["ticker"].replace("KRW-", "")
            print(f"   🔊 {name} 거래량 급증 {r['volume_ratio']:.1f}x")
        if r.get("is_surge"):
            name = r["ticker"].replace("KRW-", "")
            print(f"   ⚡ {name} 급{'등' if r['daily_change'] > 0 else '락'} {r['daily_change']:+.1f}%")

    save_portfolio(portfolio)

    # Phase 4: 리포트
    print(f"\n📁 포트폴리오 노출: {total_exposure*100:.1f}%")
    holdings = [k for k in portfolio if k not in ("_meta", "_sell_memory")]
    if holdings:
        print(f"   보유: {[t.replace('KRW-', '') for t in holdings]}")
    else:
        print("   보유 없음")

    # v3.2: VM은 매수/매도 시에만 텔레그램, 리포트는 GitHub Actions(알림 모드)에서만
    if not signal_fired and not AUTO_TRADE_ENABLED:
        status_msg = format_status_message(results, regime_info, fg)
        send_telegram(status_msg)

    print(f"\n✅ Coin Alert 완료: {utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)


if __name__ == "__main__":
    main()
