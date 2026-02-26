# 🪙 Coin Alert v3.0 — Upbit KRW 자동매매

stock-alert v7.6 로직 기반 Upbit 코인 자동매매 시스템.

## 특징
- **거래소**: Upbit KRW 마켓 (pyupbit)
- **대상**: 20종목 — 대형주(BTC, ETH, XRP, SOL, DOGE, ADA, AVAX, LINK, DOT, TRX) + 중소형(SUI, BCH, BERA, APT, VIRTUAL, AXL, ONDO, UNI, HBAR, NEAR)
- **신호**: 1시간봉 4-전략 앙상블 (추세추종 + 평균회귀 + 돌파 + 모멘텀예측) + VWAP 필터
- **자동매매**: Oracle Cloud VM (피크 15분 / 일반 30분, 24/7)
- **알림 전용**: GitHub Actions 2시간 주기
- **알림**: 텔레그램 신호 + 차트 이미지

## v3.0 변경사항
- **4번째 전략 — 모멘텀 예측**: 거래량+히스토리 기반 상승/하락 예측 모델 (7개 하위 지표)
  - OBV 다이버전스, MFI, VPT 기울기, ADL 다이버전스, Stochastic %K/%D, VWMA 이격도, MACD 히스토그램 다이버전스
  - 수학적 근거: Granville 1963(OBV), Quong & Satchell 1997(MFI), Huang et al. 2024(VWTSMOM, Sharpe 2.17)
- **포트폴리오 노출 확대**: 60% → 80% (적극적 매매)
- **VWAP 필터 완화**: 0.5x → 0.7x (유효 신호 차단 해소)
- **백테스트 거부 완화**: Sharpe<0/5회 → Sharpe<-0.5/10회 (소표본 오판 방지)
- **신뢰도 배율 선형화**: 3단계(0.4/0.7/1.0) → 연속 스케일(0.3~1.0)
- **서킷브레이커 완화**: MDD 10%→15%, 일일 5%→8% (크립토 변동성 반영)
- **라이브 시간 스탑**: 7일 보유 한도 (백테스트와 일관성)
- **ADX 3단계**: 이진(20) → 15/20/35 구간별 차등 점수

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
- **트레일링 스탑**: ATR × 2.5 (고점 추적 손절)
- **부분 익절**: ATR × 2.0 도달 시 50% 매도
- **서킷브레이커**: MDD 15% 또는 일일 낙폭 8% 시 매매 중단
- **노출 한도**: 총 80% / 종목당 최대 15%
- **상관관계 패널티**: 고상관 종목 동시 보유 시 노출 자동 감소
- **공포탐욕 연동**: 극단적 시장심리에 포지션 사이즈 자동 조정
- **시간 스탑**: 7일 이상 보유 시 자동 청산

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
