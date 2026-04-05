# Coin Alert v5.73 — Upbit KRW 시스템 매매

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

## ML 매매 분석 (v5.52 ~ v5.73)

### 목표
매도 체결 시마다 **"왜 이 거래가 수익/손실이었는가?"**를 ML이 학습할 수 있는 피처를 축적한다.
궁극적으로 **진입 시점에 "이 거래가 WIN/STUCK_LOSS가 될 확률"을 예측**하여 진입 품질을 높이는 것이 목표.

### 데이터 흐름

```
[매수]  capture_entry_context() → 매수 시점 스냅샷을 portfolio에 저장
           (RSI, ADX, BB위치, 변동성, 시장레짐, 공포탐욕 등)

[매도]  _build_webhook_extra() → 청산 시점 피처 + 진입 피처 합산
           → POST /api/v1/projects/coin-alert/trade-analysis
           → 오케스트레이터 trade_analyses DB (43컬럼)
        build_trade_features() → 동일 데이터 로컬 JSONL 백업
```

### 피처 상세 설명

#### [A] 거래 기본 (8개) — 무엇을 얼마에 사고팔았는가

| 컬럼 | 설명 |
|------|------|
| `ticker` | 종목 (예: KRW-BTC) |
| `side` | SELL 또는 PARTIAL_SELL |
| `price` | 매도 체결가 |
| `volume` | 매도 수량 |
| `krw_amount` | 매도 금액 (원화) |
| `reason` | 매도 사유 — TP1/TP2/TP3/TRAILING/RSI_SELL/SIGNAL/CATASTROPHIC_STOP/BREAKEVEN_STOP/STUCK_CLEANUP 등 |
| `entry_price` | 매수 평균단가 (DCA 시 가중평균) |
| `pnl_pct` | 수익률% = (매도가/진입가 - 1) × 100 |

#### [B] 진입 시점 기술지표 (7개) — 매수할 때 시장 상태가 어땠는가

매수 시점의 `capture_entry_context()` 스냅샷. **ML이 "어떤 조건에서 진입하면 수익이 나는가"를 학습하는 핵심 입력.**

| 컬럼 | 설명 | 좋은 진입 예시 |
|------|------|--------------|
| `entry_rsi` | 매수 시 RSI (0~100) | RSI ≤ 30 (과매도) |
| `entry_adx` | 매수 시 ADX (추세 강도) | ADX < 25 (비추세 = 평균회귀 유리) |
| `entry_bb_position` | BB 밴드 내 위치 (-1~+1, 0=중앙) | < -0.5 (하단 근접) |
| `entry_atr_pct` | 매수 시 ATR% (변동성) | 낮을수록 안정 |
| `entry_volume_ratio` | 24h 거래량 / 20일 평균 | > 1.5 (거래량 급증 = 관심 집중) |
| `entry_price_percentile` | 450봉 중 현재가 백분위 (0=최저) | < 10 (역사적 저점 근접) |
| `entry_score` | 앙상블 스코어 (3전략 합산) | 높을수록 강한 매수 신호 |

#### [C] 청산 시점 기술지표 (3개) — 팔 때 시장 상태

| 컬럼 | 설명 |
|------|------|
| `exit_rsi` | 매도 시 RSI — 높으면 과매수 구간에서 익절 |
| `exit_adx` | 매도 시 ADX — 추세 강도 |
| `exit_atr_pct` | 매도 시 ATR% — 변동성. quality_score 계산에 사용 |

#### [D] 시장 컨텍스트 (5개) — 전체 시장이 어땠는가

| 컬럼 | 설명 | ML 활용 |
|------|------|---------|
| `entry_regime` | 매수 시 BTC 레짐 (BULL/MILD_BULL/SIDEWAYS/MILD_BEAR/BEAR) | 레짐별 승률 차이 학습 |
| `exit_regime` | 매도 시 레짐 | 레짐 변화가 수익에 미치는 영향 |
| `btc_change_pct` | BTC 24h 변화율% | 시장 전체 방향성 |
| `fear_greed` | 공포탐욕지수 (0=극단공포, 100=극단탐욕) | 극단공포 매수 → 고승률 가설 검증 |
| `market_rising` | 상승 종목 수 (242종목 중) | 시장 전반 분위기 |

#### [E] 포지션 메타 (5개) — 어떻게 보유했는가

| 컬럼 | 설명 | ML 활용 |
|------|------|---------|
| `hold_hours` | 보유 시간 | 장기 보유 vs 단기 익절 패턴 |
| `dca_count` | DCA 횟수 (0/1/2) | DCA 후 승률 변화 분석 |
| `tp_level` | 익절 단계 (0=미익절, 1=TP1, 2=TP2) | 분할익절 효과 측정 |
| `max_pnl_during_hold` | 보유 중 최고 PnL% (MFE) | 최고점 대비 얼마나 회수했는지 |
| `sl_partial_done` | 분할손절 1단계 실행 여부 | 손절 이력이 최종 결과에 미치는 영향 |

#### [F] 시간 (5개) — 언제 샀고 팔았는가

| 컬럼 | 설명 | ML 활용 |
|------|------|---------|
| `entry_hour_kst` | 매수 시각 (KST 0~23) | 시간대별 승률 차이 |
| `exit_hour_kst` | 매도 시각 | - |
| `day_of_week` | 요일 (0=월 ~ 6=일) | 주말/평일 패턴 |
| `entry_is_night` | 야간 매수 여부 (23~06시 = 1) | v5.67: 83% 야간 매수 편중 발견 → 야간/주간 품질 차이 분석 |
| `exit_is_night` | 야간 매도 여부 | - |

#### [G] 라벨 (7개) — ML 학습 타깃 (이 거래가 좋았는가?)

| 컬럼 | 범위 | 설명 |
|------|------|------|
| `quality_score` | -1.0 ~ +1.0 | **핵심 라벨.** Alpha PnL + 시간효율 + 위험조정 + 레짐적합도 - 경로페널티의 가중합 |
| `alpha_pnl` | % | PnL - BTC변화율. 시장 상승분(beta)을 빼고 **순수 진입 품질(alpha)만** 측정 |
| `trade_class` | WIN/NEUTRAL/STUCK_LOSS | 3-class 분류 라벨. 소표본(~60건)에서 regression보다 견고 |
| `trade_valid` | 0/1 | PnL > 0이면 1. 메타 라벨링용 이진 타깃 |
| `mfe_capture_ratio` | -2.0 ~ 1.0 | MFE 포착률 = 최종PnL / 보유중최고PnL. **1.0=최고점 청산, 0.0=수익 전량 반납** |
| `score` | 0~100 | 거래 종합 점수 (오케스트레이터 자체 계산) |
| `rsi_delta` | | 매도RSI - 매수RSI. 양수면 과매수 방향으로 진행 |

#### [H] 리스크 파생 피처 (4개) — 거래 중 위험 신호

| 컬럼 | 설명 |
|------|------|
| `sl_distance_pct` | 손절선까지 남은 거리% — 작을수록 위험했던 거래 |
| `position_age_days` | 보유 일수 (hold_hours / 24) |
| `intra_trade_drawdown` | 보유 중 최고 PnL - 최종 PnL. **높으면 수익을 많이 반납** |
| `regime_changed` | 매수~매도 사이 레짐 변화 여부 (1=변화) — 레짐 전환이 손실 원인인지 분석 |

### ML 분류 라벨 (v5.69 — 3-class)

22건 표본 분석에서 5-class는 클래스당 ~4건으로 통계적 무의미 → **3-class로 단순화** (Codex/Gemini 합의).

| 클래스 | 조건 | 비율 | 의미 | ML 활용 |
|--------|------|------|------|---------|
| **WIN** | PnL ≥ +2% | ~60% | 설계대로 수익 실현 | 정상 패턴 학습 |
| **NEUTRAL** | -5% ~ +2% | ~25% | 노이즈/보합/소폭 손실 | 경계 조건 학습 |
| **STUCK_LOSS** | PnL ≤ -5% & 7일+ 보유 | ~15% | 구조적 진입 실패 | **집중 학습 대상** — 이 패턴을 사전 감지하는 것이 핵심 |

### quality_score 계산 (v5.65~v5.72)

```
alpha_pnl    = PnL - BTC변화율       ← 시장 수익 제거, 순수 진입 품질
pnl_score    = alpha_pnl / 10        ← [-1, +1] 정규화
time_score   = PnL / log2(보유시간+1) ← v5.72: 비선형, 짧은 거래 과대평가 방지
risk_score   = PnL / 변동성           ← 위험 대비 수익
regime_score = 레짐 보너스 + pnl      ← BULL +0.3, BEAR -0.2
path_penalty = (최고PnL - 최종PnL) × 0.015  ← 수익 반납 감점, 최대 -0.3

quality_score = 0.4×pnl + 0.1×time + 0.3×risk + 0.2×regime - path_penalty
```

### 버전별 ML 피처 추가 이력

| 버전 | 추가 피처 | 배경 |
|------|-----------|------|
| v5.52 | 기본 37컬럼 (A~F + quality_score) | ML 파이프라인 최초 구축 |
| v5.63 | max_pnl 경로 안정성 페널티 | MFE 15%→최종 3%인 거래와 0%→3%인 거래 구분 |
| v5.65 | alpha_pnl, btc_change_pct 지원 | raw PnL = beta+alpha 혼재 → 상승장 과적합 방지 |
| v5.67 | entry_is_night, entry_day_of_week | 83% 야간 매수 편중 발견 → 시간대별 품질 분석 |
| v5.69 | trade_class 3-class 분류 | 소표본에서 regression보다 견고한 classification |
| v5.70 | trade_valid 이진 라벨 | 메타 라벨링용 |
| v5.72 | mfe_capture_ratio, time_efficiency log2 | MFE 포착률로 진입품질 vs 운 분리, 짧은 거래 편향 제거 |

---

## 주요 파라미터 (v5.73)

```
SIGNAL_CANDLES             = 450          (1시간봉 ~19일)
MAX_CONCURRENT_POSITIONS   = 25           (최대 동시 보유 — v5.72: 30→25 슬롯 포화 완화)
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
CATASTROPHIC_STOP_PCT      = 30%          (상폐 방어만 — v5.71: 20→30% 복원)
TP1_BREAKEVEN_SL           = False        (v5.71: TP1 후 잔여분 버티기)
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
