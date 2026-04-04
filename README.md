# Coin Alert v5.70 — Upbit KRW 시스템 매매

평균회귀 기반 자동매매 + **손절 없이 익절만 반복**하는 구조.

## 핵심 전략
**저점에서 분할매수 → TP 도달 시 분할익절 → 반등 때까지 보유 (손절 안 함)**

> v5.53 전략 전환: 손절(-4%/-6%)로 인한 반복 손실 구조를 제거하고, 건당 비중을 5%로 쪼개 20종목 분산 보유. -30%(상폐 방어)만 손절하고 나머지는 TP 도달까지 무제한 보유.

---

## 시스템 개요

```
Upbit 전종목 스캔 (~242종목)
  → 투자유의/위험 자동 제외
  → 3-전략 앙상블 신호 생성
  → 최저가 거리 필터 (v5.50)
  → 매수 실행 (5% × 20종목 분산)
  → 보유: TP 도달까지 대기 (최대 180일)
  → 매도: 익절만 실행 (-30% 상폐 방어 제외)
  → 매매 분석 webhook → ML 피처 45+컬럼 축적
```

| 항목 | 값 |
|------|-----|
| 거래소 | Upbit KRW 마켓 (pyupbit) |
| 대상 | 전종목 자동 스캔 (~242종목) |
| 전략 | 3-전략 앙상블 (평균회귀 55-65% + 추세 5-15% + 모멘텀예측 30%) |
| 레짐 감지 | BTC 1시간봉 SMA50/200 + ADX → BULL/MILD_BULL/SIDEWAYS/MILD_BEAR/BEAR |
| 캔들 | 1시간봉 450개 (~19일), 백테스트 일봉 200일 |
| 실행 | Oracle Cloud VM, cron 피크 15분 / 일반 30분 (24/7, flock 중복방지) |
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

### 3. 최저가 거리 필터 (v5.50)

```
거리% = (현재가 / 450봉 최저가 - 1) × 100
거리%가 레짐별 한도를 초과하면 → 매수 차단
```

| 레짐 | 한도 | 의미 |
|------|------|------|
| BEAR | **5%** | 최저가 대비 5% 이내만 매수 |
| MILD_BEAR | **5%** | 동일 |
| SIDEWAYS | **7%** | 표준 |
| MILD_BULL | **10%** | 풀백 매수 허용 |
| BULL | **15%** | 추세장 여유 |

### 4. 분할매수 (DCA) — 2회

```
1차 매수: 포지션의 50% (INITIAL_BUY_RATIO = 0.5)
2차 매수(DCA1): 진입가 대비 -10% 하락 시 추가매수 (DCA_DROP_PCT = 10%)
3차 매수(DCA2): 진입가 대비 -20% 하락 시 추가매수
→ 평단 크게 낮춰서 작은 반등에도 TP1 도달
→ 백테스트: DCA 1회→2회로 승률 84→90%, MDD 18.7→8.2%
```

### 5. 포지션 구조

```
건당 비중: 5% (MAX_POSITION_PCT = 0.05)
최대 동시 보유: 20종목 (MAX_CONCURRENT_POSITIONS = 20)
최대 노출: 85%
DCA 최대: 5% × 3회 = 15% (한 종목 최대 노출)
→ 한 종목이 -30% 되어도 전체 자본 대비 -1.5~4.5% 영향
```

---

## 매도 로직

### v5.53 핵심: 손절 없이 익절만 반복

기존(v5.52 이전)의 -4%/-6% 분할 손절을 **제거**. 매도는 익절 + 상폐 방어만.

### 매도 우선순위 (위 → 아래)

#### 1. 분할 익절 (수익 구간)
| 단계 | 트리거 | 동작 | 레짐 영향 |
|------|--------|------|-----------|
| **TP1** | PnL ≥ 레짐별 TP1 | **50% 분할매도** | BEAR:2% ~ BULL:4% |
| **TP2** | PnL ≥ 8% | **잔여의 60% 매도** | 고정 |
| **TP3** | PnL ≥ 12% | **전량매도** | 고정 |

#### 2. 상폐 방어 (극단 방어만)
| 단계 | 트리거 | 동작 |
|------|--------|------|
| **CATASTROPHIC** | PnL ≤ **-30%** | 즉시 전량매도 |

#### 3. 트레일링 (수익 보호)
| 트리거 | 동작 |
|--------|------|
| 고점 PnL ≥ 5% & 고점-현재 ≥ 2% | 전량매도 |

#### 4. RSI_SELL (레짐별 과매수 익절)
| 조건 | tp_level | 동작 |
|------|----------|------|
| PnL ≥ TP1 & RSI ≥ 레짐별 | ≥ 1 | **전량매도** |
| 동일 | == 0 | **50% 분할매도** |

#### 5. 신호매도 (Churn 방지 게이트)
- 보유 ≥ 8h + PnL ≥ 0% + PnL ≥ 3%

#### 6. 장기 미회복 정리 (STUCK_CLEANUP)
| 조건 (AND) | 값 |
|------------|-----|
| 보유 기간 | ≥ **90일** |
| 최고 PnL | < **1%** (한 번도 의미있게 반등 안 함) |
| 거래대금 | < **50억** (소형주만 — BTC/ETH 등 대형주 제외) |

> 손절이 아닌 **자금 효율 관리** — 반등 가능성 극히 낮은 죽은 포지션 자금 회수

#### 제거된 것 (v5.53)
- ~~분할 SL1 (-4% → 50% 매도)~~ → **비활성**
- ~~분할 SL2 (-6% → 나머지)~~ → **비활성**
- ~~일반 SL (-5%)~~ → **30%로 상향 (상폐 방어만)**
- ~~TIME_STOP (7일)~~ → **180일 (사실상 무제한)**

---

## 레짐별 요약 (v5.53)

```
             TP1     RSI매도   SL        보유    최저가거리   진입점수
BEAR         +2%     ≥ 60     -30%만    180일   ≤ 5%        ≥ 7점
MILD_BEAR    +2.5%   ≥ 65     -30%만    180일   ≤ 5%        ≥ 7점
SIDEWAYS     +3%     ≥ 70     -30%만    180일   ≤ 7%        ≥ 6점
MILD_BULL    +3%     ≥ 75     -30%만    180일   ≤ 10%       ≥ 6점
BULL         +4%     ≥ 80     -30%만    180일   ≤ 15%       ≥ 5점
```

---

## 리스크 관리

### DD 기반 리스크 레벨
| Level | 트리거 | 대응 |
|-------|--------|------|
| 0 (정상) | — | 사이징 100% |
| **1 (주의)** | DD -3% | 사이징 **70%** |
| **2 (경고)** | DD -5% | **매수 차단** |
| 3 (서킷) | DD -8% | 전면 중단 |

### 묶임 모니터링
- 미실현 손실 포지션이 전체 보유의 **80% 이상** → 텔레그램 알림
- 자본 잠김 조기 감지 → 신규 매수 자금 부족 위험 경고

### 장기 미회복 자동 정리
- 90일+ 보유 & high_pnl < 1% & 거래대금 50억 미만 → 자동 매도
- 대형주 제외, 소형주 중 죽은 포지션만 정리하여 자금 회수

---

## ML 매매 분석 (v5.52 ~ v5.70)

### 데이터 흐름

```
매수 시: capture_entry_context() → portfolio에 entry_context 저장
매도 시: _build_webhook_extra() → 오케스트레이터 API webhook → trade_analyses DB
라벨링: _classify_trade() → 3-class (WIN/NEUTRAL/STUCK_LOSS) — v5.69
품질: compute_trade_quality_score() → Alpha PnL 기반 + 경로 안정성 페널티 — v5.65
```

### 축적 컬럼 (45+개)

| 분류 | 컬럼 |
|------|------|
| **[A] 거래** (8) | ticker, side, price, volume, krw_amount, reason, entry_price, pnl_pct |
| **[B] 진입지표** (7) | entry_rsi, entry_adx, entry_bb_position, entry_atr_pct, entry_volume_ratio, entry_price_percentile, entry_score |
| **[C] 청산지표** (3) | exit_rsi, exit_adx, exit_atr_pct |
| **[D] 시장** (5) | entry_regime, exit_regime, btc_change_pct, fear_greed, market_rising |
| **[E] 포지션** (5) | hold_hours, dca_count, tp_level, max_pnl_during_hold, sl_partial_done |
| **[F] 시간** (5) | entry_hour_kst, exit_hour_kst, day_of_week, **entry_is_night**, **exit_is_night** (v5.67) |
| **[G] 라벨** (6) | score, quality_score, **trade_valid**, **alpha_pnl**, **trade_class** (v5.69) |
| **[H] 리스크** (4) | sl_distance_pct, position_age_days, intra_trade_drawdown, regime_changed |
| **메타** (4) | id, project_id, trade_timestamp, created_at |

### ML 분류 라벨 (v5.69 — 3-class)

| 클래스 | 조건 | 의미 |
|--------|------|------|
| **WIN** | PnL ≥ +2% | 설계대로 수익 실현 |
| **NEUTRAL** | -5% ~ +2% | 노이즈/보합/회복 가능 |
| **STUCK_LOSS** | PnL ≤ -5% & 7일+ 보유 | 구조적 진입 실패 (집중 학습 대상) |

### Alpha PnL (v5.65)
- `alpha_pnl = PnL - BTC변화율` → 시장 beta 제거, 진입 품질(alpha)만 평가
- 경로 안정성 페널티: 보유 중 최고 PnL 대비 회수율 감점 (drawdown 10%p당 -0.15점)

---

## 주요 파라미터 (v5.70)

```
SIGNAL_CANDLES             = 450          (1시간봉 ~19일)
MAX_CONCURRENT_POSITIONS   = 30           (최대 동시 보유 — v5.60)
MAX_POSITION_PCT           = 0.05         (건당 5%)
MAX_PORTFOLIO_EXPOSURE     = 0.90         (최대 노출 90% — v5.62)

INITIAL_BUY_RATIO          = 0.7          (첫 매수 70% — v5.61)
DCA_DROP_PCT               = 10.0%        (DCA 트리거 — -10%/-20% 2회)
DCA_MAX_ADDS               = 2            (DCA 최대 2회 — v5.56)

# ML 분류 상수 (v5.69)
PROFIT_WIN_THRESHOLD       = 2.0%         (WIN 판정)
STUCK_LOSS_THRESHOLD       = -5.0%        (STUCK_LOSS 판정)
STUCK_HOURS_THRESHOLD      = 168h         (7일 이상 보유 → stuck)

PARTIAL_SL_ENABLED         = False        (분할 손절 비활성)
LOSS_CUT_PCT               = 30%          (상폐 방어만)
CATASTROPHIC_STOP_PCT      = 30%          (상폐 방어만)
MAX_HOLD_DAYS              = 180          (사실상 무제한)

PROFIT_TARGET_1ST          = 레짐별       (TP1: BEAR 2% ~ BULL 4%)
PROFIT_TARGET_2ND          = 8.0%         (TP2)
PROFIT_TARGET_3RD          = 12.0%        (TP3)
TRAILING_ACTIVATE          = 5.0%
TRAILING_CALLBACK          = 2.0%

RSI_BUY_CEILING            = 45
BB_STD                     = 1.6
ENTRY_LOW_DISTANCE_MAX     = {BEAR:5, MILD_BEAR:5, SIDEWAYS:7, MILD_BULL:10, BULL:15}

RISK_LEVEL_1_DD            = 3.0%         (Level 1 → 사이징 70%)
RISK_LEVEL_2_DD            = 5.0%         (Level 2 → 매수 차단)
```

---

## 백테스트 근거

25종목 200일 백테스트:

| 전략 | 승률 | 실현PnL | MDD |
|------|------|---------|-----|
| v5.52 (SL-4%/-6%, 12종목) | 48% | -33.6% | 50.5% |
| v5.53 (SL없음+DCA 1회, 20종목) | 84% | -11.8% | 18.7% |
| **v5.56 (SL없음+DCA 2회, 20종목)** | **90%** | **-0.9%** | **8.2%** |

---

## 파일 구조

```
coin-alert/
├── coin_alert.py              # 메인 매매 로직
├── trade_model.py             # ML 모델 학습/추론
├── deploy.sh                  # 배포 스크립트 (VM-로컬 해시 비교 포함)
├── trade_history.json         # 매매 히스토리 (gitignore)
├── ml_features.jsonl          # ML 피처 로그 (gitignore)
├── portfolio.json             # 포트폴리오 (gitignore)
├── order_log.json             # 주문 로그 (gitignore)
├── CLAUDE.md
├── README.md
└── .gitignore
```

## 실행 환경

- **트레이딩 VM**: Oracle Cloud (158.179.171.23) — cron으로 매매 실행
- **오케스트레이터 VM**: Oracle Cloud (146.56.119.175) — 대시보드/데일리루틴/ML API
- **webhook**: 매도 시 트레이딩VM → 오케스트레이터VM (ORCHESTRATOR_URL 환경변수)
