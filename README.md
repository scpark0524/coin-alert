# 🪙 Coin Alert — Upbit KRW 자동매매

stock-alert v7.6 로직 기반 Upbit 코인 자동매매 시스템.

## 특징
- **거래소**: Upbit KRW 마켓 (pyupbit)
- **대상**: 거래량 상위 10종목 (BTC, ETH, XRP, SOL, DOGE, ADA, AVAX, LINK, DOT, TRX)
- **신호**: 1시간봉 3-전략 앙상블 (추세추종 + 평균회귀 + 돌파)
- **실행**: GitHub Actions 30분 주기 (24/7)
- **알림**: 텔레그램 신호 + 차트 이미지

## 설정 방법

### 1. GitHub Secrets 등록
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
3. GitHub Actions IP 허용 (또는 전체 허용)

### 3. 로컬 테스트
```bash
pip install pyupbit pandas numpy requests matplotlib mplfinance
python coin_alert.py
```
> API 키 없이도 신호 분석 + 텔레그램까지 동작 확인 가능 (자동매매만 비활성)

## 리스크 관리
- **트레일링 스탑**: ATR × 2.5 (고점 추적 손절)
- **서킷브레이커**: 포트폴리오 MDD 10% 시 자동 매매 중단
- **노출 한도**: 총 80% / 종목당 최대 15%
- **상관관계 패널티**: 고상관 종목 동시 보유 시 노출 자동 감소

## 매도 조건
1. **앙상블 신호 반전** (CLOSE/STRONG_CLOSE)
2. **트레일링 스탑** (고점 - ATR × 2.5 하락)

## 파일 구조
```
coin-alert/
├── coin_alert.py           # 메인
├── .github/workflows/
│   └── coin_alert.yml      # 30분 주기 실행
├── CLAUDE.md
├── README.md
└── .gitignore
```
