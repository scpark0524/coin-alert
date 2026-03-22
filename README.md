# Coin Alert v5.49 — Upbit KRW 시스템 매매

평균회귀/스윙 트레이딩 + 레짐별 적응형 스코어링 + 분할매수매도 + ML 매매 예측.

## 핵심 원칙
**최저점 반경에서 분할매수 → 레짐별 목표에서 분할매도 → 충분히 하락하면 재매수**

---

## 시스템 개요

```
Upbit 전종목 스캔 (~241종목)
  → 투자유의/위험 자동 제외
  → 3-전략 앙상블 신호 생성
  → 최저점 반경 필터 (v5.49)
  → 리스크 레벨 체크 (v5.48)
  → ML 예측 점수 로깅 (v5.49)
  → 매수/매도 실행
  → 매매 분석 webhook → 점수 축적 → 모델 재학습
```

| 항목 | 값 |
|------|-----|
| 거래소 | Upbit KRW 마켓 (pyupbit) |
| 대상 | 전종목 자동 스캔 (~241종목) |
| 전략 | 3-전략 앙상블 (평균회귀 55-65% + 추세 5-15% + 모멘텀예측 30%) |
| 레짐 감지 | BTC 1시간봉 SMA50/200 + ADX → BULL/MILD_BULL/SIDEWAYS/MILD_BEAR/BEAR |
| 캔들 | 1시간봉 450개 (~19일), 백테스트 일봉 200일 |
| 실행 | Oracle Cloud VM, cron 피크 15분 / 일반 30분 (24/7) |
| 알림 | 텔레그램 체결 알림 |

---

## 매수 로직

### 1. 종목 필터링

| 필터 | 조건 | 비고 |
|------|------|------|
| 투자유의 | `market_event.warning = true` | 자동 제외 |
| 해외 괴리 | `caution.GLOBAL_PRICE_DIFFERENCES` | 24h 전패, 평균 -9.6% |
| 소액 집중 | `caution.CONCENTRATION_OF_SMALL_ACCOUNTS` | 작전 의심 |
| 거래대금 | 24h ≥ 30억원 | 유동성 확보 |
| 재매수 차단 | 매도가 대비 -3% 이상 하락 필요 | Churn 방지 |

### 2. 진입 조건 (AND)

| 조건 | 값 | 비고 |
|------|-----|------|
| RSI | ≤ 45 | 중립 이하만 진입 |
| BB 하단 | BB 1.6σ 이탈/근접 | 극단치 매수 |
| 앙상블 스코어 | ≥ 레짐별 임계값 (18~22) | 3-전략 복합 확인 |
| 진입 점수 | ≥ 레짐별 최소 (BULL:5 ~ BEAR:7) | RSI/BB/ADX/지지선 복합 |

### 3. 최저점 반경 필터 (v5.49)

```
백분위 = (현재가 - 450봉 최저가) / (450봉 최고가 - 450봉 최저가) × 100

백분위가 레짐별 한도를 초과하면 → 매수 차단
```

| 레짐 | 한도 | 의미 |
|------|------|------|
| BEAR | **15%** | 19일 최하위 15%만 매수 |
| MILD_BEAR | **20%** | 확실한 바닥 근처만 |
| SIDEWAYS | **25%** | 실거래 최적 구간 (승률 75%) |
| MILD_BULL | **30%** | 풀백 매수 허용 |
| BULL | **35%** | 추세 동행 여유 |

> 실거래 분석 근거: 0~20%ile 진입 승률 75%, 35%+ 진입 시 SL 집중. DOGE 사례: 저점 130, 고점 160, 매수 141=36.7%ile → 차단.

### 4. 분할매수 (DCA)

```
1차 매수: 포지션의 60% (INITIAL_BUY_RATIO = 0.6)
2차 매수: 진입가 대비 -7% 하락 시 나머지 40% (DCA_DROP_PCT = 7%)
조건: 120MA 위에서만 DCA 허용 (하락 추세 DCA 방지)
```

### 5. 리스크 레벨 (v5.48)

매 실행 시 일일 DD + 연속 SL 건수를 체크하여 사이징 조정:

| Level | 트리거 | 대응 |
|-------|--------|------|
| 0 (정상) | — | 사이징 100% |
| **1 (주의)** | DD -3% 또는 SL 2연속/6h | 사이징 **70%** |
| **2 (경고)** | DD -5% 또는 SL 3연속/6h | **매수 차단** |
| 3 (서킷) | DD -8% (기존) | 전면 중단 |

---

## 매도 로직

### 매도 우선순위 (위 → 아래)

#### Phase 1: 분할 익절 (부분매도)
| 단계 | 트리거 | 동작 | 레짐 영향 |
|------|--------|------|-----------|
| **TP1** | PnL ≥ 레짐별 TP1 | **50% 분할매도** | BEAR:3% ~ BULL:4% |
| **TP2** | PnL ≥ 8% | **잔여의 60% 매도** | 고정 |
| **TP3** | PnL ≥ 12% | **전량매도** | 고정 |

#### Phase 2: 분할 손절 (v5.48)
| 단계 | 트리거 | 동작 | 비고 |
|------|--------|------|------|
| **CATASTROPHIC** | PnL ≤ -10% | 즉시 전량매도 | MIN_HOLD 무시 |
| **TIME_STOP** | 보유 ≥ 10일 | 전량매도 | |
| **BREAKEVEN_STOP** | TP1 후 PnL ≤ 0% | 전량매도 | 진입가 이탈 시 |
| **PARTIAL_SL1** | PnL ≤ **-4%** | **50% 분할매도** | 반등 대기 |
| **STOP_LOSS (SL2)** | PnL ≤ **-6%** | **나머지 전량** | 구조적 하락 |

> SL1 실패 시 fallback: execute_sell 실패하면 PnL ≤ -5%에서 전량 SL 전환 (v5.48 fix)

#### Phase 3: 트레일링
| 트리거 | 동작 |
|--------|------|
| 고점 PnL ≥ 5% & 고점-현재 ≥ 2% | 전량매도 |

#### Phase 4: RSI_SELL (레짐별)
| 조건 | tp_level | 동작 |
|------|----------|------|
| PnL ≥ TP1 & RSI ≥ 레짐별 | ≥ 1 | **전량매도** |
| 동일 | == 0 | **50% 분할매도** |

#### Phase 5: 신호매도 (Churn 방지 게이트)
- 보유 ≥ 8h + PnL ≥ 0% + PnL ≥ 3%

---

## 레짐별 요약

```
             TP1     RSI매도   SL(분할)           백분위   진입점수
BEAR         +3%     ≥ 60     SL1-4%→50% SL2-6%   ≤ 15%    ≥ 7점
MILD_BEAR    +2.5%   ≥ 65     SL1-4%→50% SL2-6%   ≤ 20%    ≥ 7점
SIDEWAYS     +3%     ≥ 70     SL1-4%→50% SL2-6%   ≤ 25%    ≥ 6점
MILD_BULL    +3%     ≥ 75     SL1-4%→50% SL2-6%   ≤ 30%    ≥ 6점
BULL         +4%     ≥ 80     SL1-4%→50% SL2-6%   ≤ 35%    ≥ 5점
```

---

## 거래 점수 시스템 (v5.49)

### PnL 기반 연속 점수

매도 체결마다 자동 채점 → `trade_analyses` DB에 축적:

```
score = pnl_pct                              # 기본: 실제 PnL%

if hold_hours > 48:    score -= penalty       # 시간 효율 감점 (최대 -2)
if SL && hold < 4h:    score -= 1.5           # 노이즈 SL 추가 감점
if pnl < -5%:          score *= 1.5           # 큰 손실 비대칭 증폭
if pnl >= 10%:         score += 1.0           # 큰 수익 보너스
```

| 매매 예시 | PnL | 보유 | 점수 |
|----------|-----|------|------|
| TP1 +3.1% (2h) | +3.1% | 2h | **+3.10** |
| TP3 +12.4% (14h) | +12.4% | 14h | **+13.40** |
| SL -5.1% (20h) | -5.1% | 20h | **-7.65** |
| SL -5.1% (2h, 노이즈) | -5.1% | 2h | **-9.15** |
| 보유 +0.5% (5일) | +0.5% | 120h | **-1.50** |

### 축적 통계 (데일리 루틴 연동)

종목별/시간대별/사유별 점수 분포 → 데일리 루틴의 매매 리뷰 + 전략 검증에 자동 반영:
- 종목별 하위 점수 → 해당 종목 매매 패턴 분석
- 시간대별 점수 → 불리한 시간대 식별
- 사유별 PnL → 어떤 매도 전략이 효과적인지

---

## ML 매매 예측 모델 (v5.49)

### 아키텍처

```
GradientBoostingRegressor (scikit-learn)
├── 트리 50개, 깊이 3 (VM 1GB RAM 호환)
├── 모델 파일: ~50KB (trade_model.pkl)
└── 추론: <1ms
```

### 피처 (8개)

| 피처 | 범위 | 의미 |
|------|------|------|
| entry_rsi | 0~100 | 진입 시 RSI |
| exit_rsi | 0~100 | 청산 시 RSI |
| entry_score | -50~+50 | 앙상블 점수 |
| hold_hours | 0~168 | 보유 시간 |
| abs_pnl_pct | 0~15 | PnL 절대값 |
| btc_change_pct | -10~+10 | BTC 24h 변동률 |
| hour_sin | -1~+1 | 매매 시간 (순환 인코딩) |
| hour_cos | -1~+1 | 매매 시간 (순환 인코딩) |

### 학습 파이프라인

```
1. 데이터: trade_analyses DB (webhook 축적, RSI/점수 포함 데이터만)
2. 레이블: 연속 점수 (regression target)
3. 분할: Walk-Forward 80% 학습 / 20% 테스트 (시간순, 셔플 금지)
4. 평가: MAE + R2 + 방향 정확도 (수익/손실 맞춤)
5. Cold Start: 30건 미만 → 모델 비활성, 기존 로직만 사용
```

### 현재 상태

| 항목 | 상태 |
|------|------|
| 점수 축적 | 활성 (매도마다 자동) |
| 소급 데이터 | 44건 (통계용, ML 제외 — RSI 없음) |
| 실시간 데이터 | 축적 중 (30건 도달 시 첫 학습) |
| 추론 | 매수 시 예측 점수 로깅 (차단 안 함) |

### 자기 강화 루프

```
매매 체결 → 점수 축적 → 모델 재학습 → 예측 정확도 향상
    ↑                                       │
    └───────────────────────────────────────┘
```

---

## 매매 분석 시스템

### 데이터 흐름

```
coin_alert.py 매도 체결
  → record_trade()                    → trade_history.json
  → _send_trade_analysis_webhook()    → 오케스트레이터 API (비동기)
       → calc_trade_score()           → 연속 점수 계산
       → trade_analyses DB            → 22개 컬럼 축적
            ↓
  데일리 루틴 (매일 07:00 KST)
       → 축적 통계 + 최근 10건 상세 참조
       → 매매 리뷰: [TRADE ANALYSIS] 섹션
       → 전략 검증: 파라미터 실증 근거
       → 코드 수정 제안: 축적 기반 개선안
```

### 축적 컬럼 (22개)

| 분류 | 컬럼 |
|------|------|
| 거래 | ticker, side, price, volume, krw_amount, reason, entry_price, pnl_pct, hold_hours |
| 시장 | market_regime, btc_change_pct |
| 지표 | entry_rsi, exit_rsi, entry_score |
| 분석 | analysis, timing_verdict, noise_sl, optimal_exit_pct |
| 점수 | score (연속, PnL 기반) |
| 메타 | trade_timestamp, created_at |

---

## 주요 파라미터 (v5.49)

```
SIGNAL_CANDLES       = 450          (1시간봉 ~19일)
INITIAL_BUY_RATIO    = 0.6          (첫 매수 60%)
DCA_DROP_PCT         = 7.0%         (DCA 트리거)
PARTIAL_SL_1ST_PCT   = 4.0%         (분할 SL 1단계 → 50% 매도)
PARTIAL_SL_2ND_PCT   = 6.0%         (분할 SL 2단계 → 나머지)
LOSS_CUT_PCT         = 5.0%         (SL1 실패 시 fallback)
LOSS_CUT_PCT_DCA     = 4.0%         (DCA 후 SL 기준)
PROFIT_TARGET_1ST    = 레짐별        (TP1: BEAR 3% ~ BULL 4%)
PROFIT_TARGET_2ND    = 8.0%         (TP2)
PROFIT_TARGET_3RD    = 12.0%        (TP3)
TRAILING_ACTIVATE    = 5.0%
TRAILING_CALLBACK    = 2.0%
RSI_BUY_CEILING      = 45
BB_STD               = 1.6
MAX_CONCURRENT       = 12
MAX_PORTFOLIO_EXPOSURE = 0.85
ENTRY_PERCENTILE_MAX = {BEAR:15, MILD_BEAR:20, SIDEWAYS:25, MILD_BULL:30, BULL:35}
RISK_LEVEL_1_DD      = 3.0%         (Level 1 → 사이징 70%)
RISK_LEVEL_2_DD      = 5.0%         (Level 2 → 매수 차단)
```

## 파일 구조

```
coin-alert/
├── coin_alert.py              # 메인 매매 로직
├── trade_model.py             # ML 모델 학습/추론
├── trade_history.json         # 매매 히스토리 (gitignore)
├── trade_model.pkl            # 학습된 모델 (gitignore, 자동 생성)
├── portfolio.json             # 포트폴리오 (gitignore)
├── order_log.json             # 주문 로그 (gitignore)
├── backtest_*.py              # 백테스트 스크립트 (gitignore)
├── CLAUDE.md
├── README.md
└── .gitignore
```
