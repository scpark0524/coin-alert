# 🪙 Coin Alert v5.45 — Upbit KRW 자동매매 (평균회귀)

stock-alert v7.6 기반 → 평균회귀/스윙 트레이딩 + 레짐별 적응형 스코어링 + 분할매수매도.

## 핵심 원칙
**저점에서 분할매수 → 레짐별 목표 수익률에서 분할매도 → 충분히 하락하면 재매수**

## 특징
- **거래소**: Upbit KRW 마켓 (pyupbit)
- **대상**: 전종목 자동 스캔 (~241종목, 투자유의/위험 종목 자동 제외)
- **전략**: 3-전략 앙상블 (평균회귀 55-65% + 추세확인 5-15% + 모멘텀예측 30%)
- **레짐 감지**: BTC 1시간봉 기준 SMA50/200 + ADX → BULL/MILD_BULL/SIDEWAYS/MILD_BEAR/BEAR
- **자동매매**: Oracle Cloud VM (피크 15분 / 일반 30분, 24/7)
- **알림**: 텔레그램 체결 알림 + 차트 이미지

---

## 종목 필터링

### 자동 제외 대상
| 구분 | Upbit 플래그 | 제외 이유 |
|------|------------|----------|
| **투자유의** | `market_event.warning = true` | 거래지원 종료 등 심각 리스크 |
| **해외 가격 괴리** | `caution.GLOBAL_PRICE_DIFFERENCES` | 급증 후 24h 전패(0/7), 평균 -9.6% |
| **소액 계정 집중** | `caution.CONCENTRATION_OF_SMALL_ACCOUNTS` | 작전 세력 의심 |

### 차단하지 않는 Caution
| 유형 | 이유 |
|------|------|
| 거래량 급증 (TRADING_VOLUME_SOARING) | 방향성 없음 — 상승 중이면 추가 상승, 하락 중이면 추가 하락 |
| 입금량 급증 (DEPOSIT_AMOUNT_SOARING) | 단기 상승 가능 — 고점 후 하락은 SL/TP가 처리 |
| 가격 급등락 (PRICE_FLUCTUATIONS) | 변동성 증가 신호일 뿐 |

### 추가 필터
| 조건 | 값 |
|------|-----|
| 24h 거래대금 | ≥ 30억원 |
| 재매수 차단 | 매도가 대비 -3% 이상 하락해야 재진입 |

---

## 매수 로직

### 진입 조건 (AND)
| 조건 | 값 | 비고 |
|------|-----|------|
| RSI | ≤ 45 (RSI_BUY_CEILING) | 중립 이하만 진입 |
| BB 하단 이탈 | BB 1.6σ | 극단치에서만 매수 |
| 앙상블 스코어 | ≥ 레짐별 임계값 (18~22) | 3-전략 복합 확인 |
| 진입 점수 | ≥ 레짐별 최소 (BULL:5, BEAR:7) | RSI/BB/ADX/Sharpe 복합 |

### 레짐별 매수 스코어링 (get_regime_scoring)
| 레짐 | RSI 3점 | RSI 1점 | 최소 진입점수 |
|------|---------|---------|-------------|
| BEAR | RSI ≤ 20 | RSI ≤ 30 | 7점 |
| MILD_BEAR | RSI ≤ 25 | RSI ≤ 35 | 7점 |
| SIDEWAYS | RSI ≤ 30 | RSI ≤ 40 | 6점 |
| MILD_BULL | RSI ≤ 35 | RSI ≤ 45 | 6점 |
| BULL | RSI ≤ 40 | RSI ≤ 50 | 5점 |

### 분할매수 (DCA)
```
1차 매수: 포지션의 60% (INITIAL_BUY_RATIO = 0.6)
2차 매수: 진입가 대비 -5% 하락 시 나머지 40% 추가 매수 (DCA_DROP_PCT = 5%)
→ 평균단가 ~2% 개선, TP1 도달 가속
```

---

## 매도 로직

### 매도 우선순위 (위→아래 순서)

#### Phase 1: 분할 익절 (부분매도, 병렬 체크)
| 단계 | 트리거 | 동작 | 레짐 영향 |
|------|--------|------|-----------|
| **TP1** | PnL ≥ 레짐별 TP1 | **50% 분할매도** | BEAR:3%, SIDEWAYS:3%, BULL:4% |
| **TP2** | PnL ≥ 8% | **잔여의 60% 매도** | 고정 |
| **TP3** | PnL ≥ 12% | **전량매도** | 고정 |

#### Phase 2: 손절/스탑 (elif 체인, 하나만 발동)
| 단계 | 트리거 | 동작 | 비고 |
|------|--------|------|------|
| **CATASTROPHIC** | PnL ≤ -10% | 즉시 전량매도 | MIN_HOLD 무시 |
| **TIME_STOP** | 보유 ≥ 10일 | 전량매도 | |
| **BREAKEVEN_STOP** | TP1 후 PnL ≤ 0% | 전량매도 | TP1 후 진입가 이탈 시 |
| **STOP_LOSS** | DCA 미발동: PnL ≤ **-5%** | 전량매도 | 진입가 기준 |
| | DCA 발동 후: PnL ≤ **-4%** | 전량매도 | 평균단가 기준 |

> **SL 분리 근거 (v5.44)**: DCA 미발동 시 -5%로 여유있게, DCA 후에는 평균단가가 낮아졌으므로 -4%로 타이트하게. 5일 시뮬레이션에서 건당 1%p 손실 절감 확인.

#### Phase 3: 트레일링 (Phase 2에서 CLOSE 안 됐을 때)
| 트리거 | 동작 |
|--------|------|
| 고점 PnL ≥ 5% & 고점-현재 ≥ 2% | 전량매도 |

#### Phase 4: RSI_SELL (레짐별, Phase 2/3에서 CLOSE 안 됐을 때)
| 조건 | tp_level | 동작 | RSI 기준 |
|------|----------|------|----------|
| PnL ≥ TP1 & RSI ≥ 레짐별 | ≥ 1 (TP1 완료) | **전량매도** | BEAR:60 ~ BULL:80 |
| 동일 | == 0 (TP1 미완료) | **50% 분할매도** | 동일 |

> **분할매도 대원칙 (v5.40)**: RSI_SELL도 TP1 미완료 시 전량매도 대신 50% 분할매도. TP1 이상 수익에서만 발동.

#### Phase 5: 신호매도 (앙상블 CLOSE 신호, Churn 방지 게이트)
| 게이트 | 조건 |
|--------|------|
| 보유시간 | ≥ 8h |
| 손실 차단 | PnL ≥ 0 (손실이면 SL 대기) |
| 최소 PnL | PnL ≥ 3% |

---

## 레짐별 핵심 차이 요약

```
             TP1(분할)  RSI매도   SL(DCA전/후)   진입점수
BEAR         +3%       RSI ≥ 60   -5% / -4%      ≥ 7점    빨리 수익 확정
MILD_BEAR    +2.5%     RSI ≥ 65   -5% / -4%      ≥ 7점
SIDEWAYS     +3%       RSI ≥ 70   -5% / -4%      ≥ 6점    표준
MILD_BULL    +3%       RSI ≥ 75   -5% / -4%      ≥ 6점
BULL         +4%       RSI ≥ 80   -5% / -4%      ≥ 5점    추세를 충분히 탄다
```

---

## 리스크 관리
| 항목 | 값 |
|------|-----|
| 총 노출 한도 | 85% |
| 종목당 상한 | 12% |
| 동시 보유 | 최대 12종목 |
| 서킷브레이커 | MDD 15% 또는 일일 DD 8% |
| 일일 손절 한도 | 3% 또는 2회 |
| 거래대금 하한 | 30억원 (24h) |
| 손절 쿨다운 | 4시간 |
| 투자유의/위험 차단 | warning + 해외괴리/소액집중 자동 제외 |

## 주요 파라미터 (v5.45)
```
INITIAL_BUY_RATIO    = 0.6       (첫 매수 60%)
DCA_DROP_PCT         = 5.0%      (DCA 트리거)
LOSS_CUT_PCT         = 5.0%      (DCA 미발동 SL, 진입가 기준)
LOSS_CUT_PCT_DCA     = 4.0%      (DCA 후 SL, 평균단가 기준)
PROFIT_TARGET_1ST    = 레짐별     (TP1: BEAR 3%, BULL 4%)
PROFIT_TARGET_2ND    = 8.0%      (TP2: 잔여 60% 매도)
PROFIT_TARGET_3RD    = 12.0%     (TP3: 전량매도)
TRAILING_ACTIVATE    = 5.0%
TRAILING_CALLBACK    = 2.0%
RSI_BUY_CEILING      = 45
BB_STD               = 1.6
MIN_VOLUME_24H       = 30억원
MAX_CONCURRENT       = 12
MAX_PORTFOLIO_EXPOSURE = 0.85
```

## 파일 구조
```
coin-alert/
├── coin_alert.py              # 메인 (단일 파일)
├── trade_history.json         # 매매 히스토리 (영구 누적, gitignore)
├── .github/workflows/
│   └── coin_alert.yml         # GitHub Actions (2시간마다, 알림 전용)
├── CLAUDE.md
├── README.md
└── .gitignore
```

## 실행 환경
- **서버**: Oracle Cloud VM (1 OCPU / 1GB RAM + 2GB Swap)
- **실행 주기**: cron 피크 15분 (KST 21-01시, 09-10시) / 일반 30분
- **의존성**: pyupbit, pandas, numpy, requests, matplotlib, mplfinance
