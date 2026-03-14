# 🪙 Coin Alert v5.17 — Upbit KRW 자동매매 (평균회귀)

stock-alert v7.6 기반 → v5.17 평균회귀/스윙 트레이딩 + 분할매수매도.

## 핵심 원칙
**저점에서 분할매수 → 목표 수익률 도달 시 분할매도 → 충분히 하락하면 재매수**

## 특징
- **거래소**: Upbit KRW 마켓 (pyupbit)
- **대상**: 28종목 — 대형주 + 중소형 (Tier A/B/C)
- **전략**: 3-전략 앙상블 (평균회귀 55-65% + 추세확인 5-15% + 모멘텀예측 30%)
- **자동매매**: Oracle Cloud VM (피크 15분 / 일반 30분, 24/7)
- **알림**: 텔레그램 신호 + 차트 이미지

## v5.17 변경사항 (분할매수 구현)
- **INITIAL_BUY_RATIO 0.6**: 첫 매수 시 포지션의 60%만 진입
- **DCA 잔여분 자동 충당**: -3% 하락 시 나머지 40% 매수 → 평균단가 개선
- **full_position_krw 저장**: 포트폴리오에 전체 포지션 금액 기록 → DCA 잔여분 자동 계산
- **분할매도와 결합**: 분할매수(60%→100%) + 분할매도(TP1 3%→TP2 7%) 완전 순환

## 설정 방법

### 1. 환경변수 (VM: ~/coin-alert/.env)
```
TELEGRAM_BOT_TOKEN   텔레그램 봇 토큰
TELEGRAM_CHAT_ID     텔레그램 채팅 ID
UPBIT_ACCESS_KEY     Upbit Open API 접근 키
UPBIT_SECRET_KEY     Upbit Open API 시크릿 키
INITIAL_CAPITAL      초기 자본금 (KRW, 예: 5000000)
```

### 2. 로컬 테스트
```bash
pip install pyupbit pandas numpy requests matplotlib mplfinance
python coin_alert.py
```

## 매수 전략 (분할매수)
1. **1차 매수 (60%)**: 매수 신호 시 포지션의 60%만 진입
2. **2차 매수 (DCA)**: -3% 추가 하락 시 나머지 잔여분 매수 → 평균단가 개선
3. 가격 상승 시 → 60%로 TP1(+3%) 익절, 잔금은 다른 종목에 활용

## 매도 조건 (분할매도)
1. **TP1 +3%**: 60% 부분매도 (수익 확정)
2. **TP2 +7%**: 나머지 전량매도
3. **트레일링**: +5% 활성 → -2% 콜백
4. **손절 -4%** (최소 보유 2시간 후)
5. **앙상블 신호 반전** (CLOSE/STRONG_CLOSE)
6. **시간 스탑** (7일 이상 보유)

## 리스크 관리
- **RSI 매수 상한**: RSI > 55 → 매수 절대 불가
- **최소 진입 점수**: 5/10점 이상 (다중지표 복합 확인)
- **손절 쿨다운**: 손실 매도 후 4시간 재진입 금지
- **서킷브레이커**: MDD 10% 또는 일일 낙폭 8% 시 매매 중단
- **노출 한도**: 총 90% / 종목당 12% / 최대 8종목
- **거래대금**: 24h ≥ 10억원

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
