# 🪙 Coin Alert v2.2 — Upbit KRW 자동매매

stock-alert v7.6 로직 기반 Upbit 코인 자동매매 시스템.

## 특징
- **거래소**: Upbit KRW 마켓 (pyupbit)
- **대상**: 20종목 — 대형주(BTC, ETH, XRP, SOL, DOGE, ADA, AVAX, LINK, DOT, TRX) + 중소형(SUI, BCH, BERA, APT, VIRTUAL, AXL, ONDO, UNI, HBAR, NEAR)
- **신호**: 1시간봉 3-전략 앙상블 (추세추종 + 평균회귀 + 돌파) + VWAP 필터
- **자동매매**: Oracle Cloud VM 30분 주기 (24/7)
- **알림 전용**: GitHub Actions 2시간 주기
- **알림**: 텔레그램 신호 + 차트 이미지

## v2.2 변경사항
- **매수 우선순위 정렬**: TICKERS 리스트 순서 → 앙상블 점수 내림차순으로 변경
- **청산 우선 처리**: CLOSE 신호를 BUY보다 먼저 실행하여 자본 확보
- **포지션 사이징 자본 전달**: INITIAL_CAPITAL 고정 → 실제 가용 자본 반영
- **알림 모드 노출 추적**: pending_exposure 누적으로 노출 한도 체크 정상화

## v2.1 변경사항
- **서킷브레이커 _meta 오염 방지**: 알림 모드에서 _meta 갱신 차단 (`mutate_meta=False`)
- **포지션 사이징 버그 수정**: MIN_POSITION_PCT 5%→1%, fg_mult 후 재클램프
- **중복 주문 방지**: 타임스탬프 기반 쿨다운 (90분)
- **일일 낙폭**: KST 기준 리셋
- **실행 환경 이원화**: Oracle VM(자동매매) + GitHub Actions(알림 전용)

## v2.0 변경사항
- **파라미터 최적화**: RSI 9, MACD 8/21/5, BB 15/2.0, ADX 20
- **레짐 임계값 25% 인하**: 더 활발한 매매
- **VWAP 필터**: 매수=가격>VWAP, 매도=가격<VWAP (반대 방향 50% 감소)
- **부분 익절**: ATR×2.0 도달 시 50% 매도 + 나머지 트레일링
- **피라미드 매수**: 승리 포지션 1회 추가 매수 (진입가+ATR×1.0)
- **일일 낙폭 서킷브레이커**: 5% 일일 손실 시 매매 중단
- **공포탐욕 포지션 조정**: 극도공포=1.3배, 극도탐욕=0.6배
- **거래량 가중 돌파**: 3x 볼륨 부스트 (+45점)
- **Quarter-Kelly**: 켈리비율 0.25, 포트폴리오 노출 60%

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
- **트레일링 스탑**: ATR × 2.5 (고점 추적 손절)
- **부분 익절**: ATR × 2.0 도달 시 50% 매도
- **서킷브레이커**: MDD 10% 또는 일일 낙폭 5% 시 매매 중단
- **노출 한도**: 총 60% / 종목당 최대 15%
- **상관관계 패널티**: 고상관 종목 동시 보유 시 노출 자동 감소
- **공포탐욕 연동**: 극단적 시장심리에 포지션 사이즈 자동 조정

## 매도 조건
1. **앙상블 신호 반전** (CLOSE/STRONG_CLOSE)
2. **트레일링 스탑** (고점 - ATR × 2.5 하락)
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
