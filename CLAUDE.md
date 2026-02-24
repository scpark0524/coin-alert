# CLAUDE.md — Coin Alert System

## 작업 규칙
- 코드 수정 시 **README.md + 메모리 파일** 함께 업데이트 후 커밋 & 푸시
- 커밋 메시지는 한국어로 작성
- 버전 올릴 때 변경할 곳: 파일 상단 docstring, `format_status_message`, `main()` 배너

## 프로젝트 개요
- **Upbit KRW 코인 자동매매 시스템** (GitHub Actions + pyupbit + Telegram)
- 단일 파일: `coin_alert.py` (메인)
- 데이터: `portfolio.json`, `order_log.json` (gitignore)
- stock-alert v7.6 로직 기반으로 코인 특성에 맞게 조정

## 현재 상태 (v1.0)
- 10종목: BTC, ETH, XRP, SOL, DOGE, ADA, AVAX, LINK, DOT, TRX
- 신호 생성: 1시간봉 300개 (~12일)
- 백테스트: 일봉 200일 (Walk-Forward, train 150 + test 50)
- 레짐 감지: BTC 1시간봉 기준

## 핵심 로직
- 3-전략 앙상블: 추세추종 + 평균회귀 + 돌파 (레짐별 가중치)
- 포지션 사이징: inverse-ATR 기반
- 리스크: 서킷브레이커(MDD 10%), 트레일링 스탑, 상관관계 패널티
- 공포탐욕: alternative.me Crypto Fear & Greed Index

## 실행 환경
- GitHub Actions: 30분마다 (24/7)
- 의존성: pyupbit, pandas, numpy, requests, matplotlib, mplfinance
- Secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY, INITIAL_CAPITAL

## 주요 파라미터 (코인 특화)
- ATR_STOP_MULT = 2.5 (주식 2.0 → 완화)
- ATR_TARGET_MULT = 4.0 (주식 3.0 → 확대)
- RSI_OVERBOUGHT = 75 / RSI_OVERSOLD = 25
- BB_STD = 2.5 (주식 2.0)
- SIGNAL_THRESHOLD = 20 (주식 24 → 활발한 신호)
- MAX_HOLD_DAYS = 14 (일봉 환산)

## Upbit API 키 발급
1. upbit.com → 마이페이지 → Open API 관리
2. 주문하기 권한 체크
3. IP 허용 목록에 GitHub Actions IP 추가 또는 전체 허용

## 버전 히스토리
- v1.0: stock-alert v7.6 기반 초기 구현
