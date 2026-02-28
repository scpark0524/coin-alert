# 🪙 Coin Alert v3.3 — Upbit KRW 자동매매

stock-alert v7.6 로직 기반 Upbit 코인 자동매매 시스템.

## 특징
- **거래소**: Upbit KRW 마켓 (pyupbit)
- **대상**: 20종목 — 대형주(BTC, ETH, XRP, SOL, DOGE, ADA, AVAX, LINK, DOT, TRX) + 중소형(SUI, BCH, BERA, APT, VIRTUAL, AXL, ONDO, UNI, HBAR, NEAR)
- **신호**: 1시간봉 4-전략 앙상블 (추세추종 + 평균회귀 + 돌파 + 모멘텀예측) + VWAP 필터
- **자동매매**: Oracle Cloud VM (피크 15분 / 일반 30분, 24/7)
- **알림 전용**: GitHub Actions 2시간 주기
- **알림**: 텔레그램 신호 + 차트 이미지

## v3.3 변경사항 (최소 보유시간 + 자본 회전)
- **최소 보유 3시간**: 진입 직후 노이즈에 의한 스탑 발동 방지
- **매도 후 즉시 재매수**: 같은 사이클에서 CLOSE→BUY 자금 재배치 가능 (자본 회전 버그 수정)
- 분석 결과: 0~3시간 보유 거래 = 승률 0% → 스탑 유예로 개선

## v3.2 변경사항 (수익 구조 전환)
- **빠른 손절**: ATR×2.5 → 2.0 (손실 신속 차단, 쿨다운으로 보호)
- **손절 후 쿨다운**: 스탑 발동 후 같은 종목 24시간 재진입 금지 (휩소 방지)
- **v3.1 필터 제거**: RSI/BEAR/F&G 차단은 시뮬레이션에서 오히려 수익 감소 확인
- **10일 백테스트 결과**: BTC -3.7% 하락장에서 +5.7% 수익, 59% 승률, MDD 5.9%

## v3.0 변경사항
- 4번째 전략 모멘텀 예측 (7개 하위 지표), 포트폴리오 노출 80%, 서킷브레이커 완화
- VWAP 0.7x, 백테스트 거부 완화, 신뢰도 선형화, 시간 스탑 7일, ADX 3단계

## v2.x 변경사항
- v2.3: 피크 시간대 15분 실행, 종목 20개 확대, 매수 우선순위 정렬
- v2.0: VWAP 필터, 부분 익절, 피라미드, 서킷브레이커, 공포탐욕, 파라미터 최적화

## 설정 방법

### 1. 환경변수 (VM: ~/.coin-alert/.env)
```
TELEGRAM_BOT_TOKEN   텔레그램 봇 토큰
TELEGRAM_CHAT_ID     텔레그램 채팅 ID
UPBIT_ACCESS_KEY     Upbit Open API 접근 키
UPBIT_SECRET_KEY     Upbit Open API 시크릿 키
INITIAL_CAPITAL      초기 자본금 (KRW, 예: 3000000)
```

### 2. Upbit API 키 발급
1. [upbit.com](https://upbit.com/mypage/open_api_management) → Open API 관리
2. **주문하기** 권한 활성화
3. Oracle VM 고정 IP 허용

### 3. 로컬 테스트
```bash
pip install pyupbit pandas numpy requests matplotlib mplfinance
python coin_alert.py
```
> API 키 없이도 신호 분석 + 텔레그램까지 동작 확인 가능 (자동매매만 비활성)

## 리스크 관리
- **트레일링 스탑**: ATR × 2.0 (빠른 손절 + 쿨다운 보호, 최소 3시간 보유 후 적용)
- **손절 쿨다운**: 스탑 매도 후 같은 종목 24시간 재진입 금지
- **부분 익절**: ATR × 2.0 도달 시 50% 매도
- **서킷브레이커**: MDD 15% 또는 일일 낙폭 8% 시 매매 중단
- **노출 한도**: 총 80% / 종목당 최대 15%
- **상관관계 패널티**: 고상관 종목 동시 보유 시 노출 자동 감소
- **공포탐욕 연동**: 극단적 시장심리에 포지션 사이즈 자동 조정
- **시간 스탑**: 7일 이상 보유 시 자동 청산

## 매도 조건
1. **앙상블 신호 반전** (CLOSE/STRONG_CLOSE)
2. **트레일링 스탑** (고점 - ATR × 2.0 하락) + 24h 재진입 쿨다운
3. **부분 익절** (ATR × 2.0 수익 시 50% 매도)
4. **시간 스탑** (7일 이상 보유)

## 파일 구조
```
coin-alert/
├── coin_alert.py           # 메인 (단일 파일)
├── .github/workflows/
│   └── coin_alert.yml      # GitHub Actions (2시간마다, 알림 전용)
├── CLAUDE.md
├── README.md
└── .gitignore
```
