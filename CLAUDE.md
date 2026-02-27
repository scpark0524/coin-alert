# CLAUDE.md — Coin Alert System

## 작업 규칙
- 코드 수정 시 **README.md + 메모리 파일** 함께 업데이트 후 커밋 & 푸시
- 커밋 메시지는 한국어로 작성
- 버전 올릴 때 변경할 곳: 파일 상단 docstring, `format_status_message`, `main()` 배너, `meta["version"]`

## 프로젝트 개요
- **Upbit KRW 코인 자동매매 시스템** (Oracle Cloud VM + pyupbit + Telegram)
- 단일 파일: `coin_alert.py` (메인)
- 데이터: `portfolio.json`, `order_log.json` (gitignore)
- stock-alert v7.6 로직 기반으로 코인 특성에 맞게 조정

## 현재 상태 (v3.2)
- 20종목: BTC, ETH, XRP, SOL, DOGE, ADA, AVAX, LINK, DOT, TRX, SUI, BCH, BERA, APT, VIRTUAL, AXL, ONDO, UNI, HBAR, NEAR
- 신호 생성: 1시간봉 300개 (~12일)
- 백테스트: 일봉 200일 (Walk-Forward, train 150 + test 50)
- 레짐 감지: BTC 1시간봉 기준

## 핵심 로직
- 4-전략 앙상블: 추세추종 + 평균회귀 + 돌파 + 모멘텀예측 (레짐별 가중치)
- 모멘텀예측: OBV/MFI/VPT/ADL/Stochastic/VWMA/MACD히스토그램 (7개 하위 지표)
- VWAP 필터: 반대 방향 신호 30% 감소 (v3.0: 50%→30%)
- 포지션 사이징: inverse-ATR 기반 + 공포탐욕 배율 + 선형 신뢰도 배율
- 부분 익절: ATR×2.0 도달 시 50% 매도
- 피라미드 매수: 승리 포지션 1회 추가 (진입가+ATR×1.0)
- 리스크: 서킷브레이커(MDD 15% + 일일 8%), 트레일링 스탑(ATR×2.0), 시간 스탑(7일), 상관관계 패널티
- **v3.2 핵심**: 손절 후 24시간 쿨다운 (같은 종목 재진입 금지) → 휩소 방지, 승률 46%→59%

## 실행 환경
- Oracle Cloud VM: cron 피크 15분(KST 21-01시, 09-10시) / 일반 30분 (24/7)
- 의존성: pyupbit, pandas, numpy, requests, matplotlib, mplfinance
- 환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY, INITIAL_CAPITAL

## 주요 파라미터 (v3.2)
- RSI 9 / MACD 8/21/5 / BB 15/2.0 / ADX 15/20/35 (3단계)
- ATR_STOP_MULT = 2.0, ATR_TARGET_MULT = 4.0
- ATR_PARTIAL_TARGET_MULT = 2.0, PARTIAL_SELL_RATIO = 0.5
- STOP_COOLDOWN_HOURS = 24 (스탑 후 재진입 쿨다운)
- SIGNAL_THRESHOLD = 15, MAX_HOLD_DAYS = 7
- KELLY_FRACTION = 0.25, MAX_PORTFOLIO_EXPOSURE = 0.80
- DAILY_DD_LIMIT = 0.08, CIRCUIT_BREAKER_DD = 0.15

## 버전 히스토리
- v1.0: stock-alert v7.6 기반 초기 구현
- v2.0: VWAP 필터, 부분 익절, 피라미드 매수, 일일 서킷브레이커, 공포탐욕 포지션 조정, 파라미터 최적화
- v2.2: 매수 우선순위 정렬(앙상블 점수 내림차순), 실제 자본 전달, 알림 모드 노출 추적
- v2.3: 피크 시간대 15분 실행, 종목 20개 확대, 텔레그램 신뢰도 소수점 제거
- v3.0: 모멘텀 예측 전략(4번째 전략), 노출 80%, 서킷브레이커 완화, VWAP 완화, 시간 스탑
- v3.2: 빠른 손절(ATR×2.0) + 24h 쿨다운 → BTC -3.7% 하락장에서 +5.7% 수익
