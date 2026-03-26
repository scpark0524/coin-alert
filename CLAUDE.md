# CLAUDE.md — Coin Alert System

## 작업 규칙

### 수정 전 (Plan)
- **바로 코드에 손대지 말 것** — 먼저 아래 항목을 보고하고 사용자 승인 후 착수
  1. **원인 가설**: 데이터 흐름(아래 참조)에서 어느 단계가 문제인지
  2. **수정 범위**: 어떤 파일의 어떤 부분을 변경하는지
  3. **영향 범위**: 이 변경이 다른 곳(다른 VM, 다른 함수, cron 실행)에 영향을 주는지
  4. **검증 계획**: 수정 후 무엇을 어떻게 테스트하여 "고쳐졌다"고 증명할지

### 수정 중 (Execute)
- 코드 이동/리네임 시 **의존 변수 순서 검증** (사건: portfolio 로드 전 참조로 12회 크래시)
- `except` 블록에 `pass` 금지 — 최소 print/logging 필수 (사건: webhook 실패 수주간 미발견)
- VM 간 통신 URL은 **환경변수 필수**, localhost 절대 금지 (사건: webhook localhost 하드코딩)
- 커밋 메시지는 한국어로 작성

### 과거 반복 사고 패턴 (수정 시 반드시 대조)
1. **파라미터 과격 변경 → 매매 완전 차단**: MIN_VOLUME_24H 100억(v5.9), MAX_CONCURRENT 6(v4.0), TRADING_HALT=True(v5.3.1) → 매수 0건/수일. **파라미터 변경 시 "이 값이면 매매가 아예 안 될 수 있는가?" 반드시 확인**
2. **오진단 → 역효과 수정**: v5.18에서 "연쇄 SL"로 진단했지만 실제 원인은 신호매도 Churn → TP 상향이 오히려 분할매도 무력화. **증상과 원인을 구분하고, 원인을 정확히 짚은 후에만 수정**
3. **선언만 하고 미구현**: BTC_REGIME_FILTER(v5.9), validate_pre_trade()(v5.9), MIN_ENTRY_SCORE(v5.20.1) → 코드에 상수/함수 선언했으나 실제 호출부 미구현. **선언과 호출 양쪽 확인 필수**
4. **VM 코드 불일치**: AI Command Center 데일리루틴이 VM에서 직접 파라미터 변경 → Git 미커밋 → 로컬과 VM 코드 괴리(v4.6). **VM 코드 변경 시 반드시 로컬 동기화 + Git 커밋**
5. **매도 로직 순서 오류**: SL이 TIME_STOP보다 먼저 실행되어 시간스탑 기회 박탈(v5.32). **매도 우선순위: TP3 → CATASTROPHIC → TIME_STOP → BREAKEVEN → 분할SL → 트레일링 → RSI_SELL → 신호매도**
6. **분할매도 체계 우회**: RSI_SELL이 TP1 미만(+0.6%)에서 전량매도(v5.40), STRONG_CLOSE가 신호매도 가드 우회(v5.46). **새 매도 경로 추가 시 분할매도 대원칙과 신호매도 가드 모두 적용 확인**

### 수정 후 (Verify)
- `bash deploy.sh` → 해시 검증 확인
- **리얼 테스트 필수**: 실제 cron 실행 또는 수동 실행으로 동작 확인
- 검증 증거(로그, DB 조회, API 응답) 포함하여 결과 보고
- README.md + 메모리 파일 함께 업데이트 후 커밋 & 푸시
- 버전 올릴 때 변경할 곳: 파일 상단 docstring, `format_status_message`, `main()` 배너, `meta["version"]`

## 데이터 흐름 (오류 추적 시 반드시 참조)
```
[매매 실행 — cron, 트레이딩VM 158.179.171.23]
coin_alert.py
  → Upbit API (매수/매도 주문)
  → portfolio.json / order_log.json (로컬 상태)
  → trade_history.json (매매 기록 영구 보관)
  → Telegram API (체결 알림)
  ※ cron: 피크 15분(KST 21-01, 09-10) / 일반 30분, flock으로 중복 방지
  ※ 242종목 분석 ~15분 소요 — cron 겹침 시 CPU 경합으로 30분+ 지연 (사건: 3중 겹침)

[매매 분석 webhook — 트레이딩VM → 오케스트레이터VM]
coin_alert.py → $ORCHESTRATOR_URL/api/v1/projects/coin-alert/trade-analysis → trade_analyses DB
  ※ ORCHESTRATOR_URL 환경변수 필수 (.env에 정의)
  ※ localhost 절대 금지 — 트레이딩 VM에 오케스트레이터 없음 (사건: 수주간 silent fail)
  ※ except 블록에서 에러 로그 출력 필수 (pass 금지)

[대시보드 일별 P&L — 오케스트레이터VM]
trade_history.json(SSH 조회) → dashboard_data.py → 7일간 KST 날짜별 직접 집계
  ※ DB 스냅샷 미참조 — 데일리 루틴 실패해도 P&L 정상 표시 (사건: 3/22 -177원 오류)

[데일리 루틴 — 오케스트레이터VM 146.56.119.175]
APScheduler(KST 07:00) → daily_routine.py → 6단계 플로우 순차 실행
  ※ 서버 재시작 시 고아 루틴 자동 정리 (RUNNING → FAILED)

[code_apply → deploy.sh 충돌 방지]
데일리루틴 code_apply → 트레이딩VM에 SSH로 직접 수정 (v5.53 등)
deploy.sh → 로컬 코드로 트레이딩VM 덮어쓰기
  ※ deploy.sh 스텝0에서 VM-로컬 해시 비교 → 불일치 시 경고 + 확인 요청
  ※ 불일치 발생 시: VM 코드를 로컬로 먼저 가져온 뒤 deploy (scp → 로컬)

[환경변수 맵 — 트레이딩VM .env]
UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY — Upbit API 인증
TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID — 텔레그램 알림
INITIAL_CAPITAL — 초기 자본금 (현재 500만원)
ORCHESTRATOR_URL — 오케스트레이터 VM 주소 (http://146.56.119.175:8000)
```

## 프로젝트 개요
- **Upbit KRW 코인 자동매매 시스템** (Oracle Cloud VM + pyupbit + Telegram)
- 단일 파일: `coin_alert.py` (메인)
- 데이터: `portfolio.json`, `order_log.json` (gitignore)
- stock-alert v7.6 로직 기반으로 코인 특성에 맞게 조정

## 현재 상태 (v5.48)
- 전종목 자동 스캔 (~241종목, 투자유의/위험 종목 자동 제외)
- 신호 생성: 1시간봉 450개 (~19일)
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
- **v3.3 핵심**: 최소 보유 3시간 (진입 직후 노이즈 스탑 방지) → 승률 57%→59%

## 실행 환경
- Oracle Cloud VM: cron 피크 15분(KST 21-01시, 09-10시) / 일반 30분 (24/7)
- 의존성: pyupbit, pandas, numpy, requests, matplotlib, mplfinance
- 환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY, INITIAL_CAPITAL

## 주요 파라미터 (v5.48)
- 분할 익절: TP1 +3%(50%) → TP2 +8%(30%) → TP3 +12%(전량)
- 분할 손절: SL1 -4%(50%) → SL2 -6%(나머지) — v5.48 신설
- DCA: 진입가 대비 -7% 하락 시 나머지 40% 추가매수 (v5.48: 5→7%)
- 신호 캔들: 1시간봉 450개 ~19일 (v5.48: 300→450)
- STOP_COOLDOWN_HOURS = 4 (스탑 후 재진입 쿨다운)
- MAX_CONCURRENT_POSITIONS = 12, MAX_PORTFOLIO_EXPOSURE = 0.85
- CIRCUIT_BREAKER_DD = 0.15, DAILY_DD_LIMIT = 0.08

## 버전 히스토리
- v1.0: stock-alert v7.6 기반 초기 구현
- v2.0: VWAP 필터, 부분 익절, 피라미드 매수, 일일 서킷브레이커, 공포탐욕 포지션 조정, 파라미터 최적화
- v2.2: 매수 우선순위 정렬(앙상블 점수 내림차순), 실제 자본 전달, 알림 모드 노출 추적
- v2.3: 피크 시간대 15분 실행, 종목 20개 확대, 텔레그램 신뢰도 소수점 제거
- v3.0: 모멘텀 예측 전략(4번째 전략), 노출 80%, 서킷브레이커 완화, VWAP 완화, 시간 스탑
- v3.2: 빠른 손절(ATR×2.0) + 24h 쿨다운 → BTC -3.7% 하락장에서 +5.7% 수익
- v3.3: 최소 보유 3시간, 매도 후 즉시 재매수 허용 (자본 회전 버그 수정)
- v5.34~v5.46: 전종목 자동 스캔, 분할매수매도, 레짐별 적응형, 투자유의 차단 등
- v5.48: 분할 손절(SL1 -4%→50%, SL2 -6%→나머지) + DCA 간격 7% + 봉 수 450
