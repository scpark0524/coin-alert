"""
🪙 Coin Alert System v5.52 — Upbit KRW 자동매매

v5.52: ML 피처 품질 개선 + 매수 필터 전환 (2026-03-26)
- [핵심] 매수 필터: 레인지 백분위 → 최저가 거리 기반 (승률 81→85%, SL -33%)
- [신설] build_trade_features() — ML 피처 추출 + JSONL 로깅
- [신설] compute_trade_quality_score() — 매매 품질 점수 (PnL+시간효율+위험조정)
- [신설] MIN_SIGNAL_CANDLES=120 — 450봉 미달 종목 폴백
- [강화] capture_entry_context() — 매수 시점 ML 피처 스냅샷 (BUY record에 저장)
- [강화] _fetch_excluded_tickers() — 제외 사유 상세 로깅

v5.49: 최저점 반경 매수 필터 (2026-03-22)
- [핵심] 전체 캔들(450봉) 백분위 기반 매수 필터 — 레짐별 차등 한도
  BEAR 15% / MILD_BEAR 20% / SIDEWAYS 25% / MILD_BULL 30% / BULL 35%
  실거래 분석: 0~20% 진입 승률 75%, 35%+ 진입 SL 집중 → 저점 반경만 매수
- DOGE 사례: 저점 130, 고점 160, 141원 = 36.7%ile → SIDEWAYS(25%) 기준 차단

v5.48: 분할 손절 + DCA 간격 확대 + 봉 수 확장 + 리스크 모니터 (2026-03-22)
- [제안A] 분할 손절: SL 1단계(-4%)→50% 매도, SL 2단계(-6%)→나머지 전량 매도
  근거: 백테스트 SL 평균 손실 -5.83%→-2.68% (54% 감소), 반등 시 나머지 50% 회복 기회
- [제안D] DCA_DROP_PCT 5→7%: DCA 진입 간격 확대 → DCA-SL 레이스 컨디션 해소
  근거: 5% DCA 후 즉시 SL 패턴 차단, MDD 2.85%p 개선
- [제안C] SIGNAL_CANDLES 300→450: 지지/저항 정확도 향상 (~12일→~19일)
- [신설] 단계별 리스크 모니터: Level 1(DD -3%/SL 2연속)→사이징 70%, Level 2(DD -5%/SL 3연속)→매수 차단
  근거: 서킷브레이커(DD -8%) 발동 전 사전 대응, 연속 SL 시 점진적 노출 축소

v5.46: STRONG_CLOSE 신호매도 가드 누락 수정 (2026-03-22)
- [BUG] SIGNAL 매도 가드가 CLOSE에만 적용, STRONG_CLOSE 우회 → 저수익 매도 발생
- [수정] STRONG_CLOSE에도 동일 가드(MIN_SIGNAL_EXIT_PNL, 보유시간, 손실차단) 적용

v5.45: 투자위험(caution) 종목 매수 차단 (2026-03-21)
- [안전] GLOBAL_PRICE_DIFFERENCES(해외괴리) 종목 제외 — 급증 후 24h 전패, 평균 -9.6%
- [안전] CONCENTRATION_OF_SMALL_ACCOUNTS(소액집중) 종목 제외 — 작전 의심
- [구조] _fetch_warning_tickers() → _fetch_excluded_tickers() 리팩터 (warning + caution 통합)

v5.44: DCA 전/후 SL 분리 — 손절 정밀화 (2026-03-21)
- [핵심] DCA 미발동: SL -5% (진입가 기준) / DCA 발동 후: SL -4% (평균단가 기준)
- [신설] LOSS_CUT_PCT_DCA = 4% (DCA 후 전용 SL)
- [근거] 5일 시뮬레이션 5건 평균 -4.9%→-4.0%, 건당 1%p 손실 절감
- [원칙] DCA 5% 유지(의미없는 물타기 방지) + DCA 후 타이트 SL(손절최소화 대원칙2)

v5.43: Quick Fix 적용 (2026-03-21)
- [Quick Fix] LOSS_CUT_PCT 4→5 (F1+F2 해소)

v5.42: Quick Fix 적용 (2026-03-21)
- [Quick Fix] 버전 업데이트 v5.40→v5.41

v5.41: DCA/SL 역전 해소 + BEAR R:R 개선 (2026-03-21)
- [CRITICAL] DCA_DROP_PCT 5→3% / LOSS_CUT_PCT 4→5% (F1: DCA 영구 비활성 해소)
- [CRITICAL] BEAR TP1 2→3% (F3: R:R 0.5:1→0.6:1, DCA 실효 1.10:1)
- [구조] DCA-SL 간격 2%p 확보 → DCA 100% 활성화 보장 (SL 도달 전 반드시 DCA 발동)
- [R:R] BULL 실효 R:R: 0.90:1→1.37:1, BEAR 실효 R:R: 0.43:1→1.10:1
- [근거] 3인 전원 합의 CRITICAL 항목 F1/F3 즉시 해소

v5.40: RSI_SELL 분할매도 대원칙 준수 (2026-03-20)
- [CRITICAL] RSI_SELL이 TP1 미만(+0.6%~+1.28%)에서 전량매도 → 분할매도 기회 박탈 버그 수정
- [수정] RSI_SELL 최소 PnL: pnl>0 → pnl>=regime_tp1 (TP1 이상일 때만 발동)
- [수정] RSI_SELL tp_level==0: 전량매도 → TP1처럼 50% 분할매도 (대원칙4 준수)
- [수정] RSI_SELL tp_level>=1: 기존대로 전량매도 허용

v5.39: 시장추종 구조 개선 — 레짐별 적응형 스코어링 + R:R 정상화 (2026-03-19)
- [핵심] get_regime_scoring() — 레짐별 RSI 매수기준/매도기준/TP1/진입점수 동적 적용
  BEAR: RSI≤20(3점)/≤30(1점), 진입≥7, TP1 2%, RSI매도≥60
  BULL: RSI≤40(3점)/≤50(1점), 진입≥5, TP1 4%, RSI매도≥80
- [매도] RSI_SELL — 레짐별 RSI 과매수 시 이익 구간 즉시 매도 (BEAR:60, BULL:80)
- [구조] TP1_BREAKEVEN_SL 실제 구현 — TP1 후 잔여 포지션 SL을 진입가로 이동
- [R:R] LOSS_CUT_PCT 5→4% (R:R 0.3→0.38, 필요승률 77→72%)
- [DCA] DCA_DROP_PCT 3→5% (충분히 더 떨어진 뒤 물타기, DCA→SL 패턴 차단)
- [진입] BB_STD 1.3→1.6 (241종목 선택 우위 — 진짜 극단치만 매수)

v5.38: Quick Fix 적용 (2026-03-19)
- [Quick Fix] RSI 매수 윈도우 축소 — RSI_BUY_CEILING 55→45
- [Quick Fix] TP1 발동 후 잔여 포지션 손절선→진입가 이동 (TP1_BREAKEVEN_SL 신설)

v5.36: 매매 히스토리 기록 — trade_history.json (2026-03-17)
- [기능] 모든 매수/매도 시 종목, 가격, 수량, 금액, 사유, 수익률 기록
- [파일] trade_history.json — 매수(BUY/INITIAL/DCA), 매도(SELL/PARTIAL_SELL/TP1/TP2/SL 등)
- [매도 기록] entry_price + pnl_pct 포함 (해당 건의 진입가 대비 수익률)

v5.35: 투자유의(warning) 종목 매수 차단 (2026-03-16)
- [안전] Upbit market_event.warning=true 종목 TICKERS에서 자동 제외 (매수 차단)
- [근거] NOM(거래지원 종료 예정) 매수 발생 → 상폐 예정 코인 진입 방지
- [범위] 매수만 차단, 이미 보유 중인 종목은 기존 매도 로직으로 정상 처리

v5.34: Upbit KRW 전종목 자동 스캔 — 하드코딩 티커 제거 (2026-03-16)
- [전략] pyupbit.get_tickers(fiat="KRW")로 전종목 동적 조회 (~120종목)
- [근거] 상장/상폐 자동 대응, 진입 필터가 허술한 종목 자동 차단
- [안전] API 실패 시 10종목 폴백 리스트 사용

v5.33: 동시 보유 종목 8→12 확대 — 자본 활용률 개선 (2026-03-16)
- [전략] MAX_CONCURRENT_POSITIONS 8→12 (60% 첫매수×12=86%, 85% 노출 상한이 자연 캡)
- [근거] 유휴자금 과다 — 실제 노출 10%대, DCA 미발동 시 42% 유휴

v5.32: 손절최소화 대원칙 정비 — 매도 순서 재설계 (2026-03-16)
- [CRITICAL] 라이브 매도 순서 수정: TP3→CATASTROPHIC→TIME_STOP→SL (SL이 TIME_STOP보다 먼저 발동 수정)
- [CRITICAL] 백테스트 매도 순서 동기화 + CATASTROPHIC_STOP/TRAILING_STOP 추가
- [원칙] 손절최소화: SL은 모든 다른 EXIT(TP/TRAILING/TIME) 이후 최후의 수단

v5.31: 정비 — 5건 버그 일괄 수정 (2026-03-16)
- [CRITICAL] MIN_SIGNAL_EXIT_PNL 1.0→3.0% 실제 적용 (v5.27~v5.29 로그만 기록, 상수 미변경)
- [BUG] _sell_memory 불일치 오경보 수정 (actual_set에서 _sell_memory 제외 누락)
- [CLEANUP] MIN_VALID_ENTRY_PRICE 유령 상수 제거, EOS/FLOW 티커 제거

v5.30: Quick Fix 적용 (2026-03-16)
- [Quick Fix] 버전 및 변경 로그 업데이트

v5.29: MIN_SIGNAL_EXIT_PNL 미적용 재수정 (2026-03-16)
- [CRITICAL] MIN_SIGNAL_EXIT_PNL 1.0→3.0% 재적용 (v5.27 로그만 기록, 실제 값 미변경 확인)
- [증상] v5.28 이후에도 TP1(3%) 이전 전량매도 재발 → 상수 값 1.0 잔존
- [순서] TP1(3%)→Signal Exit(3%+)→Trailing(5%)→TP2(8%)→TP3(12%)

v5.28: Quick Fix 적용 (2026-03-16)
- [Quick Fix] 버전 및 변경 로그 업데이트

v5.27: 신호매도 TP1 하회 전량매도 차단 (2026-03-16)
- [CRITICAL] MIN_SIGNAL_EXIT_PNL 1.0→3.0% (TP1 이하 전량 신호매도 차단)
- [근거] SHIB +1% 전량 매도 — 분할매도(TP1 3%) 기회 박탈, 대원칙4 위배
- [판단] 신호매도는 TP1 이후에만 허용, 분할매도 우선순위 보장
- [순서] TP1(3%)→Signal Exit(3%+)→Trailing(5%)→TP2(8%)→TP3(12%) 충돌 없음

v5.26: Quick Fix 적용 (2026-03-16)
- [Quick Fix] 네트워크 재시도 상수 및 유틸리티 import 추가

v5.24: Quick Fix 적용 (2026-03-16)
- [Quick Fix] 버전 및 변경 로그 업데이트

v5.23: MIN_VALID_ENTRY_PRICE 제거 (2026-03-15)
- [CRITICAL] MIN_VALID_ENTRY_PRICE 상수 및 로직 전면 제거
- [근거] 단가<1원 코인(SHIB 0.02원, PEPE 0.01원) 정상 진입가를 "0원 오류"로 오판
- [증상] entry_price→current_price 덮어쓰기 → PnL=0% → 수수료 -0.1% 매도 발동
- [판단] 0원 방어는 매수 시점 검증으로 충분 — 매도 루프 내 사후 검사 불필요

v5.22: Quick Fix 적용 (2026-03-16)
- [Quick Fix] 버전 및 변경 로그 업데이트
- [Quick Fix] RSI_SELL_TRIGGER 72→75 (조기매도 완화 — 최우선)
- [Quick Fix] PROFIT_TARGET_2ND 7.0→8.0 (TP2 상향)
- [Quick Fix] PROFIT_TARGET_3RD 10.0→12.0 (TP3 stretch 상향)
- [Quick Fix] MIN_VALID_ENTRY_PRICE 상수 신설 (진입가 0원 방어)

v5.21: EXIT 구조 상향 + 진입가 무결성 게이트 (2026-03-15)
- [전략] RSI_SELL_TRIGGER 72→75 (20연속 조기매도 교훈 — 과매수 확정 후 매도)
- [전략] TP2 7→8%, TP3 10→12% (R:R 1.89→2.3 목표, trailing 5%와 간격 확보)
- [CRITICAL] MIN_VALID_ENTRY_PRICE 1원 신설 (SHIB 0원 사고 — 진입가 무결성 게이트)
- [검증] 20/20 후속상승 평균 +6.4% → RSI75 + TP2(8%) 구조가 수익 포착 개선
- [순서] TP1(3%)→Trailing(5%)→TP2(8%)→TP3(12%) 충돌 없음 확인

v5.20.1: 손실 구간 신호매도 차단 + 3단계 분할익절 (2026-03-15)
- [CRITICAL] 신호매도는 이익(PnL≥+1%) 시에만 허용 — 손실 시 SL/TIME_STOP이 전담
- [FIX] ETC -2.8% SIGNAL 매도 방지 (대원칙2 "손절은 최후의 수단" 위배)
- [전략] 3단계 분할익절: TP1 +3%(50%) → TP2 +7%(30%) → TP3 +10%(전량)
- [전략] MAX_CONCURRENT 6→8 복원 (Churn 근절 후 히스토리 축적 목적)
- [전략] MAX_PORTFOLIO_EXPOSURE 80→85% (자본 효율 + DCA 여력 균형)

v5.20: 신호매도 Churn 방지 — 동일가 매수매도 근절 (2026-03-15)
- [CRITICAL] MIN_SIGNAL_EXIT_HOURS 8h 신설 (신호매도 최소 보유 8h — 2h 후 0% 매도 방지)
- [CRITICAL] MIN_SIGNAL_EXIT_PNL 1.0% 신설 (PnL<+1% 신호매도 차단 — 수수료 소모 방지)
- [CRITICAL] SIGNAL_EXIT_THRESHOLD -10→-15 (더 강한 반전 신호만 매도 허용)
- [복원] TP1 4→3% (v5.16 복원 — 신호매도 전에 분할매도 발동해야 함)
- [복원] TP2 10→7% (v5.16 복원 — 순차 구조 유지)
- [조정] SL 6→5% (4%/6% 절충 — 노이즈 SL 방지 + CATASTROPHIC 간격 확보)
- [조정] MAX_CONCURRENT 5→6 (기회 축소 완화)
- [유지] DAILY_LOSS_LIMIT 3%, MAX_SL_PER_DAY 2 (v5.18 안전장치 유지)
- [검증] 백테스트: Churn 28→0건, 승률 64→70%, 총수익 +6.9%p 개선

v5.19: Quick Fix 적용 (2026-03-15)
- [Quick Fix] SL 확대 — 중소알트 정상 노이즈 커버 (4% → 6%)
- [Quick Fix] TP1 상향 — R:R 비대칭 완화 (3% → 4%)
- [Quick Fix] TP2 상향 — 잔여 포지션 stretch 타겟 (7% → 10%)
- [Quick Fix] 동시보유 축소 — 상관관계 연쇄SL 방지 (8 → 5)
- [Quick Fix] 포트폴리오 익스포저 정상화 (90% → 80%)
- [Quick Fix] 일일 손실 서킷브레이커 신설 (신규 상수 2개)

v5.17: 분할매수 구현 — 첫 진입 60%만 매수 (2026-03-14)
- [전략] INITIAL_BUY_RATIO 0.6 신설 (첫 매수 시 포지션의 60%만 진입)
- [전략] DCA가 나머지 40% 자동 충당 (-3% 하락 시 잔여분 매수)
- [목적] 평균단가 개선 → 수익률 도달 가속, 추격매수 방지
- [안전] full_position_krw 저장 → DCA 금액 = 포지션 잔여분 자동 계산

v5.16: 분할매도 활성화 — TP1 3%/TP2 7%/Trailing 5% (2026-03-14)
- [전략] TP1 5→3% (신호매도 전 분할매도 발동, 빈번한 수익 확정)
- [전략] TP2 10→7% (TP1 대비 ~2.3× 비율, 순차 구조 유지)
- [전략] TRAILING_ACTIVATE 7→5% (TP1→Trailing→TP2 순차 충돌 없음)
- [목적] 많은 종목 분할매수매도 → 꾸준한 수익률 모델 구축

v5.15: Quick Fix 적용 (2026-03-14)
- [Quick Fix] RSI_OVERSOLD 40→35 (과매도 기준 강화)
- [Quick Fix] MIN_ENTRY_SCORE 4→5 (다중지표 복합 진입 복귀)
- [Quick Fix] 24h 가격위치 필터 상수 신설 (PRICE_PERCENTILE_BLOCK)

v5.13: 분산 매매 전환 — 히스토리 축적 우선 (2026-03-13)
- [전략] MAX_CONCURRENT 3→8 (소액 다종목 분산, 매매 빈도 극대화)
- [전략] MAX_POSITION_PCT 20→12% (종목당 ~60만원, 과집중 방지)
- [전략] MAX_PORTFOLIO_EXPOSURE 80→90% (유휴 자본 축소)
- [전략] MIN_VOLUME_24H 30→10억 (중소형 알트 진입 확대)
- [목적] 수익 극대화보다 반복 매매 히스토리 축적 → 로직 강화 데이터 확보
- [안전] 종목당 SL 최대 -2.4만원(0.48%), 전종목 동시 SL -19.2만원(3.8%)

v5.12: Quick Fix 적용 (2026-03-13)
- [Quick Fix] BTC_REGIME_FILTER hard block 비활성화 (전면 차단 → 개별 필터 의존)

v5.10: Quick Fix 적용 (2026-03-13)
- [Quick Fix] MIN_ENTRY_SCORE 5→4 (진입 확률 최대 영향 파라미터 #2)

v5.9: ë§¤ì ì°¨ë¨ ë²ê·¸ ìì  (2026-03-13)
- [CRITICAL] MIN_VOLUME_24H 100->30ìµ (ì  ì¢ëª© ì°¨ë¨ í´ì)
- [CRITICAL] vol_24h candle->Upbit API (ì íë ê°ì )
- [êµ¬í] BTC_REGIME_FILTER 20MA ê¸°ë° êµ¬í
- [ìì ] INITIAL_CAPITAL .env 500ë§ ëê¸°í
- [ìì ] ë°°ë ë²ì  ëì  ì¶ì¶
- [ê²ì¦] 3ì¼ ë°±íì¤í¸: 7ê±´ ì¹ë¥ 100% +3.68%

v5.8: BTC 레짐 필터 단축 (2026-03-12)
- [조정] BTC_REGIME_MA_PERIOD 30→20 (risk-off 과잉 지속 해소)

v5.7: 쿨다운 과잉 차단 해소 (2026-03-12)
- [조정] STOP_COOLDOWN_HOURS 6→4h (야간 손절 후 오전 차단 해소)
- [조정] ORDER_COOLDOWN_MINUTES 120→60분 (실매수 미체결 대응)

v5.6: 진입 기회 확대 (2026-03-12)
- [조정] RSI_OVERSOLD 35→40, BB_STD 1.5→1.3, MIN_ENTRY_SCORE 6→5
- [조정] MIN_VOLUME_24H 200→100억원 (유니버스 병목 해소)

v5.5: 분산 투자 정상화 (2026-03-12)
- [조정] MAX_CONCURRENT_POSITIONS 2→3 (증액 반영)

v5.4: Ticker 유니버스 확대 + 자금 증액 (2026-03-11)
- [확대] Tier A 4종 추가: EOS, XLM, ETC, PEPE (500억+ 유동성 검증)
- [확대] Tier B 6종 추가: ARB, SEI, STX, ATOM, AAVE, IMX (200억+ 실시간필터)
- [제외] OP (ARB과 ρ=0.82, 동일 섹터 중복 → ARB만 편입)
- [섹터] L1/L2 편중 → 결제(XLM), DeFi(AAVE), 게이밍(IMX) 분산
- [자금] INITIAL_CAPITAL 200만→300만원 (포지션 사이징 정상화)
- [기대] 일 진입 기회 0.54→0.9건, 포지션 슬롯 활용률 27%→45%
- [안전] MIN_VOLUME_24H=200억 실시간 필터 유지 → 유동성 미달 자동 제외

v5.3: 결함 3건 구조적 수정 + 안전장치 함수 신설 (2026-03-11)
- [CRITICAL] validate_pre_trade() 신설 — 쿨다운/포지션한도/유동성 3중 게이트
- [CRITICAL] get_effective_config() 신설 — DERISK_MODE 실효 적용
- [CRITICAL] scan_ghost_positions() 신설 — 고아 포지션 실시간 탐지
- [정리] VIRTUAL TICKERS 제거 (3/10 전량 청산 완료)
- [운영] DERISK_MODE 플래그→실행 로직 구현

v5.2: 실행 결함 수정 + 구조적 리스크 패치 (2026-03-10)
- [CRITICAL] VIRTUAL 종목 복원 (고아 포지션 TP1 미실행 버그)
- [CRITICAL] CATASTROPHIC_STOP 15→10% (SAHARA SL 오버런 교훈)
- [포지션] MAX_CONCURRENT 3→2 (상관관계 리스크 — 전 부문 합의)
- [유동성] MIN_VOLUME_24H 150억→200억 (SL 오버런 방지)
- [운영] DERISK_MODE 신설 (HALT↔정상 중간 단계)
- [주석] MIN_HOLD_HOURS/MIN_ENTRY_SCORE 오류 수정

v4.5: 변동성/지지저항 필터 조정
- [필터] VOLATILITY_THRESHOLD 5.0→3.0, SR_PROXIMITY 0.015→0.025

v4.4: 실전 데이터 기반 익절/RSI 최적화
- [익절] TP1 5.0→3.5%, TP2 10.0→7.0%
- [RSI] RSI_OVERBOUGHT 70→75, RSI_SELL_TRIGGER 68→78
- [시간] STOP_COOLDOWN 12→6h, MIN_HOLD 4→2h

v4.3: 포지션/트레일링/추세 필터 개선
- [포지션] MAX_POSITION_PCT 15→20%, MAX_HOLD 7→10일
- [트레일링] TRAILING_ACTIVATE 5%, TRAILING_CALLBACK 2.0%
- [신설] SIGNAL_EXIT_THRESHOLD, 추세 필터

v4.2: AND→스코어링 구조 전환 (7일 실전 0.02% 체결률 대응)
- [구조] AND 6중 필터 → 가중 스코어링 (10점 만점, 4점 이상 진입)
- [구조] 고정 포지션 → 신호 강도 비례 사이징 (50/75/100%)
- [진입] RSI_OVERSOLD 40→45, RSI_BUY_CEILING 65→70
- [진입] BB_STD 1.5→1.2σ (신호 +72%)
- [진입] ADX_STRONG_TREND 28→40 (약추세 진입 허용)
- [진입] VOLUME_SPIKE 1.3→1.0 (24h 거래대금으로 단일화)
- [손절] -3→5% (코인 변동성 적합, 대원칙#2 준수)
- [익절] TP1 2.5→2.0% (BB 1.2σ 회귀거리 보상)
- [보유] 5→8일 (SL -5% 복원 여유)
- 예상 진입 확률: 0.13%→8-12% (스코어링 기준)

v4.0: 평균회귀 전면 재설계 (breakout 제거, 고정 TP/SL)
v3.x: 모멘텀 추종 (고점 매수 문제로 폐기)
v2.x: VWAP, 부분 익절, 피라미드, 서킷브레이커
v1.0: stock-alert v7.6 기반 코인 자동매매
"""

import pyupbit
import pandas as pd
import numpy as np
import requests
import os
import json
import time
from datetime import datetime, timezone, timedelta

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf

# 네트워크 재시도 설정 (v5.25)
API_RETRY_COUNT     = 3        # API 호출 실패 시 최대 재시도 횟수
API_RETRY_DELAY     = 2        # 재시도 간격 (초), 지수 백오프 적용: 2→4→8초
API_TIMEOUT         = 10       # API 요청 타임아웃 (초)

def safe_api_call(func, *args, max_retries=API_RETRY_COUNT, **kwargs):
    """네트워크 오류 시 지수 백오프 재시도 래퍼"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError,
                ConnectionResetError,
                OSError) as e:
            wait = API_RETRY_DELAY * (2 ** attempt)
            if attempt < max_retries - 1:
                print(f"[NET_RETRY] {func.__name__} 실패 ({attempt+1}/{max_retries}): {e} — {wait}초 후 재시도")
                time.sleep(wait)
            else:
                print(f"[NET_FAIL] {func.__name__} {max_retries}회 실패: {e}")
                return None
    return None

# ============================================
# 설정
# ============================================
# v5.34: Upbit KRW 전종목 자동 조회 (하드코딩 제거)
# 진입 필터(RSI, 거래대금, 진입점수 등)가 허술한 종목을 걸러주므로 전종목 스캔해도 안전
# API 실패 시 기존 관리 종목으로 폴백
TICKERS_FALLBACK = [
    # 대형주
    "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE",
    "KRW-ADA", "KRW-AVAX", "KRW-LINK", "KRW-DOT", "KRW-TRX",
    "KRW-XLM", "KRW-ETC", "KRW-PEPE",
    # 중형주
    "KRW-SUI", "KRW-BCH", "KRW-APT", "KRW-ONDO", "KRW-UNI",
    "KRW-HBAR", "KRW-NEAR", "KRW-ARB", "KRW-SEI", "KRW-STX",
    "KRW-ATOM", "KRW-AAVE", "KRW-IMX",
    # 소형주 + 고변동
    "KRW-SHIB", "KRW-TRUMP", "KRW-AXS", "KRW-YGG", "KRW-TAO",
    "KRW-RENDER", "KRW-VIRTUAL", "KRW-BSV", "KRW-MNT", "KRW-BERA",
    "KRW-SAHARA", "KRW-IP",
]

def _fetch_excluded_tickers():
    """Upbit 투자유의(warning) + 투자위험(caution) 종목 조회.

    차단 대상:
    - warning=true: 거래지원 종료 등 (기존)
    - caution.GLOBAL_PRICE_DIFFERENCES: 해외 가격 괴리 (급증 후 24h 전패, 평균 -9.6%)
    - caution.CONCENTRATION_OF_SMALL_ACCOUNTS: 소액 계정 집중 (작전 의심)
    """
    DANGEROUS_CAUTIONS = {"GLOBAL_PRICE_DIFFERENCES", "CONCENTRATION_OF_SMALL_ACCOUNTS"}
    warned = set()
    cautioned = set()
    warning_reasons = {}   # {ticker: [reason, ...]} — ML 추적용
    caution_reasons = {}
    try:
        resp = requests.get("https://api.upbit.com/v1/market/all?is_details=true", timeout=10)
        if resp.status_code == 200:
            for m in resp.json():
                if not m["market"].startswith("KRW-"):
                    continue
                ticker = m["market"]
                ev = m.get("market_event", {})
                if ev.get("warning"):
                    warned.add(ticker)
                    warning_reasons[ticker] = "warning"
                caution = ev.get("caution", {})
                if isinstance(caution, dict):
                    matched = [f for f in DANGEROUS_CAUTIONS if caution.get(f)]
                    if matched:
                        cautioned.add(ticker)
                        caution_reasons[ticker] = "/".join(matched)
    except Exception as e:
        print(f"   ⚠️ 투자유의/위험 조회 실패: {e}")
    # 상세 로깅 (ML 데이터 추적용)
    if warned:
        names = [t.replace("KRW-", "") for t in warned]
        print(f"   ⚠️ 투자유의 제외: {', '.join(names)}")
    if cautioned:
        for t, reasons in caution_reasons.items():
            print(f"   🚫 투자위험 제외: {t.replace('KRW-', '')} ({reasons})")
    return warned, cautioned

def fetch_krw_tickers():
    """Upbit KRW 마켓 전종목 자동 조회. 투자유의/위험 종목 제외. 실패 시 폴백."""
    try:
        tickers = pyupbit.get_tickers(fiat="KRW")
        if tickers and len(tickers) > 10:
            warned, cautioned = _fetch_excluded_tickers()
            excluded = warned | cautioned
            if excluded:
                tickers = [t for t in tickers if t not in excluded]
                if warned:
                    print(f"   ⚠️ 투자유의 제외: {', '.join(t.replace('KRW-','') for t in warned)}")
                if cautioned:
                    print(f"   🚫 투자위험 제외: {', '.join(t.replace('KRW-','') for t in cautioned)} (해외괴리/소액집중)")
            print(f"   ✅ Upbit KRW 전종목 조회: {len(tickers)}종목")
            return tickers
    except Exception as e:
        print(f"   ⚠️ 티커 조회 실패, 폴백 사용: {e}")
    return TICKERS_FALLBACK

TICKERS = fetch_krw_tickers()
INITIAL_CAPITAL = int(os.environ.get("INITIAL_CAPITAL", 5_000_000))  # KRW 500만원 기본

# 캔들 설정
SIGNAL_INTERVAL = "minute60"   # 신호 생성용: 1시간봉
SIGNAL_CANDLES  = 450          # 1시간봉 450개 (~19일) — 지지/저항 정확도 향상
BT_INTERVAL     = "day"        # 백테스트용: 일봉
BT_CANDLES      = 200          # 일봉 200일

# 기술적 지표 (v4.0: 평균회귀 특화)
SHORT_WINDOW        = 20
LONG_WINDOW         = 50
RSI_PERIOD          = 9
RSI_OVERBOUGHT      = 70       # v5.0: 68→70 (Wilder 표준 과매수, SELL_TRIGGER 72와 2pt 버퍼)
                               # 근거: 68은 중립 근접, 정상 변동에 잦은 경고 → 알림 피로
                               # 70 = 표준 과매수 임계, 72 = 매도 실행 → 경고(70)→실행(72) 명확
                               # 대원칙4 "올랐을 때 확실히 익절" — 70 경고 후 72 즉시 실행
RSI_OVERSOLD        = 35       # v5.14: 40→35 (v5.6 완화의 부작용 — RSI40은 과매도 미달, 고점 진입 허용)
                               # 근거: RSI 35 = 하위 ~20%ile, 반등 성공률 ~62% (40의 58% 대비 +4%p)
                               # v5.13 실전: RSI 40 통과 후 즉시 하락 → 수수료 손실 거래 발생
                               # MIN_ENTRY_SCORE 5 + BB 1.3σ 복합 조건으로 진입 빈도 보완
                               # RSI_BUY_CEILING(55)로 상방 이중 차단 유지
                               # 대원칙3 "충분히 떨어졌을 때만 진입" — 35는 명확한 과매도 구간
RSI_BUY_CEILING     = 45       # v5.37: 55→45 (3/18 RSI45~55 진입 5건 반등률 0%, -52,500원 직접 손실)
                               # 근거: RSI 35~45 = 과매도 확정→초기 반등 구간, 반등 성공률 ~68%
                               # RSI 45~55 = 중립 복귀 구간, 반등 미확정 — 추격매수 위험
                               # 매수 윈도우 20pt→10pt 축소, MIN_ENTRY_SCORE 5와 결합 시 품질 유지
                               # 대원칙3 "충분히 떨어졌을 때만 진입" — 45 이상은 중립, 과매도 미달
RSI_SELL_TRIGGER    = 75       # v5.21: 72→75 (20연속 조기매도 교훈 — RSI72는 반등 초입에서 발동)
                               # 근거: RSI75 = 상위~8%ile, 72(~12%ile) 대비 매도 4%p 지연
                               # 20/20 후속상승 +6.4% 평균 — RSI72가 반등 중간에서 조기 발동
                               # RSI 경고(70) → 실행(75): 5pt 버퍼, 경고 후 확인 매도
                               # TP1(3%)+Trailing(5%) 작동 후 RSI75 도달 시 추가 확정
                               # 대원칙4 "올랐을 때 확실히 익절" — 75는 과매수 확정 구간
MACD_FAST           = 8
MACD_SLOW           = 21
MACD_SIGNAL         = 5
BB_PERIOD           = 15
BB_STD              = 1.6      # v5.39: 1.3→1.6 (241종목 선택 우위 — 진짜 극단치만 매수)
                               # 근거: 1.5σ는 MIN_ENTRY_SCORE 6과 결합 시 진입 마비 유발
                               # 1.3σ 반등 성공률 ~60% (1.5σ 65% 대비 -5%p, 1.2σ 52% 대비 +8%p)
                               # MIN_ENTRY_SCORE 5 + RSI 40 + BB 1.3σ = 복합 품질 유지
                               # v4.2(1.2σ)보다 보수적, v4.7(1.5σ)보다 현실적 — 중간점
                               # 대원칙3 준수: BB 하단 근처 = "충분히 떨어진" 가격대 확인
ADX_PERIOD          = 14
ADX_STRONG_TREND    = 40       # v4.2: 28→40 (ADX28은 약추세까지 차단 → 과잉필터링)
                               # 근거: ADX 28~40 = 중간추세, 평균회귀 여전히 유효한 구간
                               # ADX 40+ = 강한 추세, 역추세 진입 위험 현실화 → 여기서 차단
                               # Wilder 기준: 40+ 에서만 "명확한 강추세" — 실전 적합
                               # 스코어링 시스템에서 ADX<25 가산점 부여로 품질 보완
VOLUME_SPIKE_RATIO  = 1.0      # v4.2: 1.3→1.0 (거래대금 필터(24h≥15억)로 유동성 이미 확보)
                               # 근거: 캔들 단위 거래량 스파이크는 진입 장벽일 뿐, 수익과 무상관
                               # 1.0 = 실질 비활성화, 스코어링에서 vol>1.5x 시 가산점으로 전환
                               # 이중 유동성 필터 제거 → 단일 24h 필터로 단순화
PRICE_CHANGE_THRESHOLD = 3.0   # v4.5: 5.0→3.0 (1h봉에서 5% 변동은 상위3%ile, 사실상 블랙스완 필터)
                               # 근거: 3% = 의미있는 가격 변동 확인에 충분한 임계값
                               # 대형 코인(BTC/ETH) 1h 평균 변동 1.5~2.5% → 3%는 평균+1σ 수준

# 스코어링 시스템 (v4.2 신설)
MIN_ENTRY_SCORE     = 6        # v5.39: 5→6 (기본값, 레짐별 get_regime_scoring()이 우선 적용)
                               # 근거: 4점은 RSI(3)+ADX_low(1)로 사실상 RSI 단독 트리거
                               # v5.13 실전: 4점 진입 7건 중 완결 1건 수수료 손실 → 품질 부족
                               # 5점 = RSI 과매도

# R:R 구조 개선 (v5.37 신설)
TP1_BREAKEVEN_SL    = True     # v5.37: TP1 발동 후 잔여 포지션 SL→진입가 이동
                               # 근거: TP1(3%) 50% 매도 후, 잔여 50%가 SL(-5%)로 손실 전환 방지
                               # 수리적: TP1 후 반전 시 순손익 -1.0%→+1.5% (R:R 구조 정상화)
                               # 대원칙2 "손절 최소화" — 이익 확정 포지션의 손실 전환 차단

# 과매매 방지 (v5.37 신설)
MAX_DAILY_BUYS      = 5        # v5.37: 일 매수 건수 상한 (3/18 13건 과매수 방지)
                               # 근거: 13건/일 매수 → 슬롯 포화, 자본 희석, 수수료 과다
                               # 5건/일 = 8슬롯 기준 63% 교체율, 충분한 기회 + 품질 유지(3) + BB 하단(2) 복합 확인 → 반등 확률 +10%p
                               # 포지션 사이징: score 5=50%, 6=75%, 7+=100% 유지
                               # 진입 빈도 감소 감수 — 거래 품질 > 거래 빈도 (대원칙1)
                               # 대원칙3 "충분히 떨어졌을 때만" — 복합 시그널로 확인
SR_LOOKBACK         = 60
SR_PROXIMITY        = 0.025    # v4.5: 0.015→0.025 (S/R 자체 오차 ±1~2% 감안, 2.5%가 실용적 근접 범위)
                               # 근거: 지지선에서 1.5% 이내만 인정하면 터치 없이 반등하는 경우 놓침
                               # 2.5% = S/R 반등 유효 범위의 실증적 상한

# v5.14 신설: 24h 가격위치 필터 (고점 추격매수 차단)
PRICE_PERCENTILE_BLOCK = 70    # 24h 고저 범위 대비 현재가 위치 — N%ile 이상 진입 차단
PRICE_PERCENTILE_PENALTY = 3   # 가격위치 필터 위반 시 스코어 감점 (3점)

# v5.50: 최저가 기준 거리 매수 필터 (v5.49 레인지 백분위에서 전환)
# 변경: (현재가-최저가)/(최고가-최저가) → (현재가/최저가 - 1) × 100 [최저가 대비 거리%]
# 근거: 20종목 200일 백테스트 — 승률 81.2%→85.5%, SL 12→8건, 평균PnL +6.17→+6.74%
# 최고가에 영향받지 않아 급등 후 하락장에서 왜곡 없음
ENTRY_LOW_DISTANCE_MAX = {
    "BEAR":       2,   # 최저가 대비 2% 이내만 — 확실한 바닥
    "MILD_BEAR":  3,   # 3% 이내 — 보수적
    "SIDEWAYS":   5,   # 5% 이내 — 표준
    "MILD_BULL":  7,   # 7% 이내 — 상승 초기 완화
    "BULL":      10,   # 10% 이내 — 추세장 풀백 허용
}

# 포지션 사이징 (v4.0: 분산 테스트)
RISK_BUDGET             = 0.02
MAX_POSITION_PCT        = 0.12   # v5.13: 20→12% (분산 매매 — 8종목×12%=96%, 과집중 방지)
                                 # 근거: 코인 간 상관계수 높아 10종목 분산 효과 제한적
                                 # 5종목 × 20% = 100% → MAX_PORTFOLIO_EXPOSURE(80%)로 상한 유지
                                 # 외부 고문: "농도 짙은 매매가 관리 효율 면에서 우월"
MIN_POSITION_PCT        = 0.01
MAX_PORTFOLIO_EXPOSURE  = 0.85   # v5.20.1: 80→85% (DCA 여력 15% 확보 + 자본 효율 개선)
                                 # 근거: 8종목×12%=96% → 85%에서 7종목까지 진입, DCA 여력 15%
                                 # 80%는 과보수적 — Churn 근절(v5.20.1) 후 추가 기회 확보 필요
                                 # 대원칙1 "수익 극대화" + 대원칙5 "하락장에서 포지션 구축" 균형
MAX_CONCURRENT_POSITIONS = 12    # v5.33: 8→12 (자본 활용률 개선 — 60% 첫매수×12=86%, 85% 노출 상한이 캡)
                                 # 근거: v5.18이 줄인 이유는 "연쇄 SL"이었으나 실제 원인은 신호매도 Churn
                                 # v5.20.1에서 손실 구간 신호매도 완전 차단 → Churn 없이 8종목 분산 가능
                                 # 최악 시나리오: 8 × 60만 × SL(-5%) = -24만원(-4.8%)
                                 # MDD(15%)까지 10.2%p 여유 — 안전 마진 충분
                                 # 500만원 투입 목적: 다종목 매매 히스토리 축적 → 로직 강화
                                 # 대원칙1 "수익 극대화" — 진입 기회 확대, 자본 효율 개선

# 켈리 참고용
KELLY_FRACTION          = 0.25   # v2.0: 0.5→0.25 Quarter-Kelly
MIN_TRADES_FOR_KELLY    = 10
DEFAULT_WIN_RATE        = 0.55
DEFAULT_WIN_LOSS_RATIO  = 1.5

# 비용 (업비트 수수료 0.05% 매수+매도 = 10bps)
COMMISSION_BPS      = 5
SLIPPAGE_BPS        = 5
TOTAL_COST_BPS      = COMMISSION_BPS + SLIPPAGE_BPS

# v4.0: 고정 수익률 기반 리스크 관리
ATR_PERIOD      = 14
ATR_STOP_MULT   = 2.0           # 백테스트 호환용
ATR_TARGET_MULT = 4.0           # 백테스트 호환용
PROFIT_TARGET_1ST    = 3.0      # v5.20: TP1 — 빈번한 수익 확정 (평균회귀 1~2σ 반등폭)
                                # 대원칙4 "목표 수익률 도달 시 주저 없이 매도" — 3%에서 즉시
PROFIT_TARGET_2ND    = 8.0      # v5.21: 7→8% (R:R 개선, trailing 5%와 3%p 간격 확보)
                                # TP1(3%)→Trailing(5%)→TP2(8%) 순차 구조, 충돌 없음
                                # 20/20 후속상승 중앙값 +5.8% — TP2(8%)는 상위 반등에서 확정
                                # 잔여 50%의 60% = 전체 30% 매도, R:R 기여 +0.3%p
PROFIT_TARGET_3RD    = 12.0     # v5.21: 10→12% (stretch 타겟 확대, 강한 추세 최대 포착)
                                # TP2(8%)→TP3(12%) 4%p 간격, 충돌 없음
                                # 20/20 최대 후속상승 +15.3% — 12%는 상위 반등 시 도달 가능
                                # 잔여 20%만 해당 → 미도달 시 trailing(5%)이 수익 보호
                                # 대원칙1 "수익 극대화" — 잔여 포지션으로 상방 극대화
PARTIAL_SELL_RATIO_1 = 0.5      # v5.20.1: TP1에서 50% 매도 (가장 빈번한 TP — 절반 확정)
                                # TP1(50%) + TP2(30%) + TP3(20%) = 100%
                                # 대원칙4 "올랐을 때 확실히 익절" — 3%에서 절반 즉시 확정
PARTIAL_SELL_RATIO_2 = 0.6      # v5.20.1: TP2에서 잔여의 60% 매도 (전체 기준 30%)
                                # TP1 후 잔여 50% × 60% = 30% 매도
                                # TP3용 잔여 20% 유지
                                # 대원칙1 "수익 실현이 최우선" — 단계별 확정 비중 분산
LOSS_CUT_PCT        = 5        # v5.44: DCA 미발동 시 SL (진입가 기준 -5%)
                               # 코인 일간 변동 3~5% → 5%는 노이즈 SL 방지 + DCA 기회 보장
LOSS_CUT_PCT_DCA    = 4        # v5.44: DCA 발동 후 SL (DCA 평균단가 기준 -4%)
                               # DCA로 평단 하락 → 좁은 SL로 손실 최소화 (대원칙2)
                               # 시뮬레이션: 5건 평균 -4.9% → -4.0%, 건당 1%p 손실 절감
                                # 근거: SL 5% vs TP1 3% = R:R 0.3 → 승률 77% 필요 (비현실적)
                                # SL 4% = R:R 0.38, 필요승률 72% (진입필터 강화로 달성 가능)
                                # DCA(-5%) 후 평균가 기준 ~2.0% 여유, 반등 관찰 1~2캔들
                                # 대원칙2 "손절은 최후의 수단" — 좁은 SL + 높은 진입 품질로 보완
# v5.48 신설: 분할 손절 — 수익은 분할매도, 손절도 분할매도 (비대칭 해소)
PARTIAL_SL_ENABLED     = True   # 분할 손절 활성화
PARTIAL_SL_1ST_PCT     = 4.0    # SL 1단계: -4% → 50% 매도 (손실 확정 최소화)
                                # 근거: 기존 전량 SL(-5%) 대비 1단계에서 절반만 확정
                                # 반등 시 나머지 50%로 손실 회복 기회 확보
PARTIAL_SL_2ND_PCT     = 6.0    # SL 2단계: -6% → 나머지 전량 매도 (추가 하락 방어)
                                # 근거: 1단계(-4%) 후 2%p 추가 하락 = 구조적 하락 판단
PARTIAL_SL_RATIO       = 0.5    # 1단계 매도 비율 (50%)
                                # 백테스트: SL 평균 -5.83% → -2.68% (54% 감소)
CATASTROPHIC_STOP_PCT = 10.0    # v5.2: 15→10% (SAHARA -10% 사고 시 15%는 미발동 구간)
                                # 근거: 10% = SL(-4%) 대비 2.5배, 갭다운 슬리피지 포함 커버
                                # SAHARA 교훈: -100% 도달 전 -10%에서 차단했으면 손실 1/10
                                # 일반 SL(-4%)과 6%p 간격 → 정상 변동/DCA에 간섭 없음
                                # 즉시 시장가 전량 매도, MIN_HOLD_HOURS 무시
                                # 대원칙2 "손절은 최후의 수단" — 10%는 구조적 붕괴 임계

# v5.48 신설: 단계별 리스크 레벨 (서킷브레이커 사전 대응)
RISK_LEVEL_1_DD = 3.0     # Level 1 (주의): 일일 DD -3% 또는 SL 2연속
RISK_LEVEL_2_DD = 5.0     # Level 2 (경고): 일일 DD -5% 또는 SL 3연속
RISK_LEVEL_1_SIZE = 0.7   # Level 1: 포지션 사이징 70%로 축소
RISK_LEVEL_2_SIZE = 0.0   # Level 2: 신규 매수 차단
RISK_SL_LOOKBACK_HOURS = 6  # 최근 6시간 내 연속 SL 카운트

# v5.18 신설: 일일 손실 서킷브레이커 (3/14 4연속 SL 교훈)
# v5.20.1: DAILY_LOSS_LIMIT_PCT, MAX_SL_PER_DAY 제거
# 이유: 대원칙5 "하락장에서 포지션 구축" — SL 발동 후가 오히려 저점 매수 기회
# 매수 차단은 대원칙1 "수익 극대화"에 위배. 개별 종목 리스크는 SL(-5%)이 담당.
REBUY_DROP_PCT       = 3.0      # v4.2: 5→3% (평균회귀 사이클에 맞는 재진입 허용)
STOP_COOLDOWN_HOURS  = 4        # v5.7: 6→4h (실매수 미체결 대응 — 야간 손절 후 오전 차단 해소)
                                # 근거: 6h는 새벽 손절 시 오전 세션 진입 차단 (03시SL→09시해제)
                                # 4h = 1h봉 4개 경과, 시장 상황 충분히 변화 + 감정적 재진입 방지
                                # 24h 마켓에서 4h = 1/6 세션, 아시아→유럽 전환점에서 재진입 허용
                                # 대원칙5 "코인은 반드시 오르고 내린다" — 빠른 사이클 활용
MIN_HOLD_HOURS       = 2        # v4.4: TP/SL 매도용 최소 보유시간 (급등 시 TP1 즉시 실현 허용)
                                # 근거: 2h = 1h봉 2개, 수수료 대비 마진 확보 최소 시간
MIN_SIGNAL_EXIT_HOURS = 8       # v5.20 신설: 신호매도(SIGNAL) 전용 최소 보유시간
                                # 근거: 2h에서 SIGNAL 매도 → 0% PnL 동일가 Churn 다수 발생 (3/14)
                                # 8h = 1h봉 8개, 평균회귀 전략이 작동할 최소 시간
                                # TP/SL/TRAILING은 2h 유지 (수익/손절은 즉시 실행 필요)
                                # 대원칙5 "코인은 반드시 오르내린다" — 사이클에 시간을 줘야 함
MIN_SIGNAL_EXIT_PNL  = 3.0      # v5.29: 1.0→3.0% (TP1 이하 전량 신호매도 차단)
                                # 근거: SHIB +1% 전량 매도 → 분할매도(TP1 3%) 기회 박탈
                                # 순서: TP1(3%)→Signal Exit(3%+)→Trailing(5%)→TP2(8%)→TP3(12%)
                                # 대원칙2 "손절은 최후의 수단, 반등 기회를 기다리라" 위배
                                # 신호매도 = 이익 실현 도구 (PnL ≥ +1% 시만 허용)
                                # 손실 퇴장 = SL(-5%) / CATASTROPHIC(-10%) / TIME_STOP(7일)이 전담
                                # 대원칙1+2 "이익일 때 팔고, 손실은 SL까지 기다리라"
MAX_HOLD_DAYS        = 7        # v5.0: 10→7일 (DCA 1회 체제에서 반등 완성 5~7일 충분)
                                # 근거: DCA_MAX_ADDS=1 축소 → "2회 DCA 후 10일 대기" 근거 소멸
                                # 7일 = 주간 사이클 1회, 미반등 시 기회비용 > 추가 대기 가치
                                # 대원칙5 "코인 사이클 활용" — 1주 내 미반등 = 추세 전환 의심
SIGNAL_THRESHOLD       = 15     # 진입 전용: RSI+BB 강한 신호 2개면 매수 허용
SIGNAL_EXIT_THRESHOLD  = -15    # v5.20: -10→-15 (더 강한 반전만 매도 — Churn 방지)
                                # 근거: -10은 앙상블 +20→-10 (30p 이동)으로 수시간 내 도달
                                # -15는 RSI 과매수 + BB 상단 + MACD 반전 등 복합 확인 필요
                                # 3/14 교훈: -10에서 동일가 SIGNAL 매도 다수 발생 → 수수료만 소모
                                # 대원칙5 "코인은 반드시 오르내린다" — 약한 반전은 노이즈

# v5.17: 분할매수 (첫 진입 일부 + DCA로 나머지 충당)
INITIAL_BUY_RATIO      = 0.6     # v5.17 신설: 첫 매수 시 포지션의 60%만 진입
                                 # 근거: 평균회귀 전략에서 첫 진입가가 최저가인 경우는 드묾
                                 # 60% 진입 후 가격 상승 → 그대로 TP1(3%)에서 익절
                                 # 60% 진입 후 가격 하락 → DCA로 나머지 40% 저가 매수, 평단 개선
                                 # 대원칙3 "충분히 떨어졌을 때만 진입" — 분할로 추격 리스크 분산
DCA_ENABLED            = True    # v4.0: 분할매수 활성화
DCA_DROP_PCT           = 7.0     # v5.48: 5→7% (DCA-SL 레이스 해소, 백테스트 MDD 2.85%p 개선)
                                 # 근거: 5% DCA 후 SL 4% = 1%p 간격 → 즉시 SL, 손실 확대
                                 # 7% DCA → 평균가 기준 SL까지 ~4%p, 진짜 바닥에서만 DCA 실행
                                 # v5.39 5%에서도 DCA→SL 패턴 지속 → 더 엄격한 간격 필요
                                 # 대원칙3 "충분히 떨어졌을 때만 진입" — DCA 트리거 최엄격
DCA_MAX_ADDS           = 1       # v4.7: 2→1회 (실전: 2회 DCA 시 총 노출 200%, 실질 DD -12.5%)
                                 # 근거: 1회 DCA = 총 150% 노출, 실질 최대 DD -7.5%로 제한
                                 # 하락 추세에서 3레이어 동시 손실 방지 (대원칙2 준수)
                                 # TREND_FILTER와 결합: 120MA 아래 시 DCA 0회(진입만)
DCA_ADD_RATIO          = 0.5     # v5.17: 기존 50%는 fallback용 (full_position_krw 없는 레거시 포지션)
                                 # 신규 포지션: full_position_krw - 현재보유금액 = 잔여분 자동 계산

# v4.3 신설: 추세 필터 (하락 추세 DCA 방지)
TREND_MA_PERIOD        = 120     # 120봉 이평선 (1시간봉 기준 5일)
DCA_TREND_FILTER       = True    # True: 가격이 120MA 아래일 때 DCA 횟수를 1회로 제한
                                 # 근거: 계단식 하락에서 DCA는 손실 규모를 키우는 독
                                 # 대원칙2 "손절 최소화" — V자 반등 맹신 방지

# v5.1 신설: BTC 레짐 필터 (시장 방향성 게이트)
BTC_REGIME_FILTER      = False   # v5.11: hard block 비활성화 (3일 연속 전종목 0건 거래 마비 해소)
                                 # 진단: 50→30→20 MA 단축에도 BTC 지속 하락 → 전 알트 차단 유지
                                 # 리스크매니저 권고: "20이 하한, 추가 단축 대신 필터 재설계 필요"
                                 # 하방 방어 잔존: SL(-4%) + CATASTROPHIC(-10%) + DAILY_DD(8%)
                                 # 개별 스코어링(RSI+BB+ADX ≥ 4점)이 종목별 품질 게이트 역할
                                 # 최악 시나리오: 3종목 × 100만 × SL(-4%) = -12만(-2.4%)
                                 # TODO: score penalty 방식 재설계 (BTC risk-off → score -2점)
                                 # 대원칙1 "수익 극대화" — 완전 차단은 수익 기회 전면 소멸
BTC_REGIME_MA_PERIOD   = 20      # v5.8: 30→20 (v5.7 30MA에서도 오후까지 risk-off 지속 → 추가 단축)
                                 # 근거: BTC 30MA(~30h)는 1.5일+ 하락 시 반등 감지 불가 (3/12 오후 재확인)
                                 # → 오전+오후 다수 알트 시그널 전량 차단, 일 진입 0건 지속
                                 # 20MA(~20h) = 당일 BTC 반등 시 risk-on 전환 (약 1캘린더일)
                                 # 15MA는 4~6h 노이즈 바운스에 false risk-on 위험 → 20이 하한
                                 # 하방 방어: SL(-4%) + CATASTROPHIC(-10%) + DAILY_DD(8%) 3중 유지
                                 # 데드캣바운스 리스크: 포지션당 20% × SL 4% = 최대 -0.8% 자본 손실
                                 # 대원칙1 "수익 극대화" — BTC 과잉 차단이 수익 기회 전면 소멸시킴

# v4.1: 거래대금 필터 (유동성 리스크 차단)
MIN_VOLUME_24H         = 3.0e9   # v5.37: 10→30억 (전종목 스캔 후 소형 고위험 알트 과다 진입 방지)
                                 # 근거: 200억 필터 시 28종 중 5종만 통과(82% 즉시 탈락) → 진입 마비
                                 # 100억 = 종목당 100만원 주문 대비 일거래량 0.001%, 슬리피지 5~10bps
                                 # SAHARA 교훈은 CATASTROPHIC_STOP(10%) + 포지션사이징(20%)으로 대응
                                 # 28종 중 200억 미달~100억 이상 구간: SUI, BCH, APT, ONDO 등 편입
                                 # 대원칙1 "수익 극대화" — 유동성 과잉 필터가 수익 기회 차단 방지

# v4.1: 트레일링 익절 (수익 보존)
TRAILING_ACTIVATE_PCT  = 5.0     # v5.16: 7→5% (TP1 3.0% 부분매도 후 +2.0%p 추가 상승 확인)
                                 # 근거: TP1(3.0%)→Trailing(5.0%)→TP2(7.0%) 순차 구조
                                 # 5% + callback 2% = 최소 종료가 +3.0% (TP1 레벨 정확 보호)
                                 # TP2(7%)와 2%p 간격 → 독립 작동, 레벨 충돌 없음
TRAILING_CALLBACK_PCT  = 2.0     # v4.3: 1.5→2.0% (크립토 1h봉 평균 변동폭 1.5% 감안)
                                 # 근거: 1.5% 콜백은 정상 변동에도 트리거 → 2.0%로 노이즈 필터

# 서킷브레이커
CIRCUIT_BREAKER_DD = 0.15  # v3.0: 10%→15% 크립토 변동성 반영
DAILY_DD_LIMIT     = 0.08  # v3.0: 5%→8% 회복 시간 확보

# 중복 주문 방지 (v2.1: 타임스탬프 기반)
ORDER_COOLDOWN_MINUTES = 60   # v5.7: 120→60분 (실매수 미체결 대응 — 쿨다운 과잉 차단 해소)
                              # 근거: 120분은 야간 매도 후 오전 시그널을 2시간 차단
                              # 60분 = 1h봉 1개, 시장 재평가 + 라운드트립 방지에 충분
                              # v4.7 라운드트립 2건 → 60분에서도 동일 방어 (30분→발생, 60분→미발생)
                              # 대원칙1 "수익 극대화" — 합법적 시그널 불필요 차단 방지 왕복 거래 방지

# ML 학습 데이터 수집 설정 (v5.52)
ML_FEATURE_LOG      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml_features.jsonl")
ML_MIN_SAMPLES      = 100
ML_SCORE_WEIGHTS    = {"pnl": 0.4, "time_efficiency": 0.2, "risk_adjusted": 0.3, "regime_fit": 0.1}
MIN_SIGNAL_CANDLES  = 120   # 450봉 미달 종목 폴백 (RSI14 + BB20 + 여유분)

# 파일 경로
_BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE  = os.path.join(_BASE_DIR, "portfolio.json")
ORDER_LOG_FILE  = os.path.join(_BASE_DIR, "order_log.json")
TRADE_HISTORY_FILE = os.path.join(_BASE_DIR, "trade_history.json")

# 환경변수
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")
UPBIT_ACCESS_KEY    = os.environ.get("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY    = os.environ.get("UPBIT_SECRET_KEY")
ORCHESTRATOR_URL    = os.environ.get("ORCHESTRATOR_URL", "")  # 오케스트레이터 VM 주소 (예: http://146.56.119.175:8000)

AUTO_TRADE_ENABLED = all([UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY])

# v5.0: 안전 중단 플래그 (True: 신규 매수 전면 차단, 기존 포지션 청산/모니터링만 허용)
# CODE RED 시 systemctl stop 대신 이 플래그를 True로 변경 → 고아 포지션 방지
# 사용법: TRADING_HALT = True → 재가동 시 False
# v5.2: 2단계 운영 모드 (Codex 고문 de-risk mode 권고 반영)
# TRADING_HALT = True  → 신규 매수 전면 차단, 기존 포지션 자동 청산 로직만 가동
# DERISK_MODE  = True  → 신규 매수 차단 + DCA 비활성 + 동시보유 1개 제한 (축소 운영)
# 둘 다 False          → 정상 운영
TRADING_HALT = False  # v5.3.1: HALT 해제 → 정상 운영 복귀 (2026-03-11)
                      # 해제 절차: ① 슬리피지 반영 백테스트 양의 EV 확인
                      #           ② BTC 50MA 상방 확인 (레짐 필터)
                      #           ③ DERISK_MODE=True 단계 먼저 경유 (축소 운영)
                      # v5.3: validate_pre_trade()로 결함 3건 구조적 방지 완료
DERISK_MODE  = False  # v5.3.1: 정상 운영 복귀 (백테스트 자동검증 체계 구축 완료)
                      # True 시: 신규진입 차단, DCA 비활성, MAX_CONCURRENT=1로 오버라이드
                      # HALT 해제 시 DERISK_MODE=True → 검증 후 False 순차 복귀 권장


KST = timezone(timedelta(hours=9))  # v2.1: 한국 표준시


def utc_now():
    return datetime.now(timezone.utc)


# ============================================
# v5.3: 운영 모드 제어 + 매매 전 안전 체크
# ============================================

def get_effective_config():
    """TRADING_HALT/DERISK_MODE에 따른 실효 파라미터 반환

    Returns:
        dict: max_concurrent(int), dca_enabled(bool), new_entry_allowed(bool)
    """
    cfg = {
        'max_concurrent': MAX_CONCURRENT_POSITIONS,
        'dca_enabled': DCA_ENABLED,
        'new_entry_allowed': True,
    }
    if TRADING_HALT:
        cfg['new_entry_allowed'] = False
        cfg['dca_enabled'] = False
    elif DERISK_MODE:
        cfg['new_entry_allowed'] = False
        cfg['dca_enabled'] = False
        cfg['max_concurrent'] = 1
    return cfg


def _get_24h_trade_value(ticker):
    """Upbit 24시간 누적 거래대금(KRW) 조회 — REST API 직접 호출

    Args:
        ticker: 마켓 코드 (예: 'KRW-BTC')
    Returns:
        float or None: 24h 누적 거래대금(KRW), 실패 시 None
    """
    try:
        resp = requests.get(
            "https://api.upbit.com/v1/ticker",
            params={"markets": ticker},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                return float(data[0].get('acc_trade_price_24h', 0))
    except Exception:
        pass
    return None


def validate_pre_trade(ticker, portfolio, order_log, is_dca=False):
    """매매 전 3중 안전 체크 — 결함 D1/D2/D3 구조적 방지

    Args:
        ticker: 매매 대상 종목 (예: 'KRW-BTC')
        portfolio: 포트폴리오 dict (positions 키 포함)
        order_log: 주문 로그 list (각 항목에 ticker, timestamp 키)
        is_dca: True이면 DCA 매수 (포지션 한도 체크 스킵)
    Returns:
        list[str]: 위반 사항 목록 (빈 리스트 = 통과, 매수 허용)
    """
    errors = []
    cfg = get_effective_config()

    # Gate 0: 운영 모드 체크
    if not is_dca and not cfg['new_entry_allowed']:
        mode = "HALT" if TRADING_HALT else "DERISK"
        errors.append(f"[{mode}] 신규 매수 차단 중")
        return errors
    if is_dca and not cfg['dca_enabled']:
        mode = "HALT" if TRADING_HALT else "DERISK"
        errors.append(f"[{mode}] DCA 비활성")
        return errors

    # Gate 1: 포지션 한도 (신규 진입 시만 — D3 방지)
    if not is_dca:
        positions = (portfolio or {}).get('positions', {})
        active_count = sum(
            1 for p in positions.values()
            if isinstance(p, dict) and p.get('status') == 'active'
        )
        if active_count >= cfg['max_concurrent']:
            errors.append(
                f"포지션 한도 초과: {active_count}/{cfg['max_concurrent']}"
            )

    # Gate 2: 쿨다운 (신규/DCA 모두 — D2 방지)
    now = utc_now()
    for entry in reversed(order_log or []):
        if entry.get('ticker') == ticker:
            try:
                last_ts = datetime.fromisoformat(entry['timestamp'])
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                elapsed_min = (now - last_ts).total_seconds() / 60
                if elapsed_min < ORDER_COOLDOWN_MINUTES:
                    errors.append(
                        f"쿨다운 위반: {ticker} {elapsed_min:.0f}분 전 거래 "
                        f"(필요: {ORDER_COOLDOWN_MINUTES}분)"
                    )
            except (ValueError, KeyError):
                pass
            break

    # Gate 3: 유동성 (D1 방지)
    vol_24h = _get_24h_trade_value(ticker)
    if vol_24h is not None and vol_24h < MIN_VOLUME_24H:
        errors.append(
            f"유동성 부족: {ticker} 24h거래대금 "
            f"{vol_24h / 1e8:.0f}억 < {MIN_VOLUME_24H / 1e8:.0f}억"
        )

    return errors


def scan_ghost_positions():
    """Upbit 잔고 스캔 → TICKERS 미등록 보유 종목 탐지 (고아 포지션 방지)

    Returns:
        list[dict]: 고아 포지션 목록
            [{'ticker': str, 'balance': float, 'value_krw': float, 'avg_price': float}]
    """
    ghosts = []
    if not AUTO_TRADE_ENABLED:
        return ghosts
    try:
        upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
        balances = upbit.get_balances()
        ticker_set = set(TICKERS)
        for bal in balances:
            currency = bal.get('currency', '')
            if currency == 'KRW':
                continue
            ticker = f"KRW-{currency}"
            balance_amt = float(bal.get('balance', 0))
            avg_price = float(bal.get('avg_buy_price', 0))
            value_krw = balance_amt * avg_price
            # 5,000원 이상만 유의미한 포지션으로 판단
            if value_krw > 5000 and ticker not in ticker_set:
                ghosts.append({
                    'ticker': ticker,
                    'balance': balance_amt,
                    'value_krw': value_krw,
                    'avg_price': avg_price,
                })
    except Exception:
        pass
    return ghosts


# ============================================
# 텔레그램 알림
# ============================================
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ 텔레그램 토큰/챗ID 미설정 — 알림 건너뜀")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ 텔레그램 전송 성공")
        else:
            print(f"❌ 전송 실패: {response.status_code}")
    except Exception as e:
        print(f"❌ 텔레그램 네트워크 오류: {e}")


def send_telegram_photo(image_bytes, caption=""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        if len(caption) > 1024:
            caption = caption[:1020] + "..."
        files = {"photo": ("chart.png", image_bytes, "image/png")}
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"}
        response = requests.post(url, data=data, files=files, timeout=30)
        if response.status_code == 200:
            print("✅ 텔레그램 차트 전송 성공")
        else:
            print(f"❌ 차트 전송 실패: {response.status_code}")
    except Exception as e:
        print(f"❌ 텔레그램 차트 네트워크 오류: {e}")


# ============================================
# 포트폴리오 & 주문 이력
# ============================================
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 포트폴리오 로드 실패: {e}")
    return {}


def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)


def load_order_log():
    if os.path.exists(ORDER_LOG_FILE):
        try:
            with open(ORDER_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_order_log(log):
    with open(ORDER_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def has_recent_order(log, ticker, direction, cooldown_minutes=ORDER_COOLDOWN_MINUTES):
    """v2.1: 타임스탬프 기반 중복 주문 방지 (쿨다운 방식)"""
    key = f"{ticker}_{direction}"
    last_time_str = log.get(key)
    if not last_time_str:
        return False
    try:
        last_time = datetime.fromisoformat(last_time_str)
        elapsed = (utc_now() - last_time).total_seconds() / 60
        return elapsed < cooldown_minutes
    except (ValueError, TypeError):
        return False


def record_order(log, ticker, direction):
    key = f"{ticker}_{direction}"
    log[key] = utc_now().isoformat()
    # 오래된 항목 정리 (24시간 이상 된 것)
    cutoff = utc_now() - timedelta(hours=24)
    stale = []
    for k, v in log.items():
        try:
            if datetime.fromisoformat(v) < cutoff:
                stale.append(k)
        except (ValueError, TypeError):
            stale.append(k)
    for k in stale:
        del log[k]
    save_order_log(log)


# ============================================
# ML 피처 수집 (v5.52)
# ============================================
def compute_trade_quality_score(pnl_pct, holding_hours, volatility, regime):
    """매매 품질 점수 — ML 학습 라벨. 범위 -1.0 ~ +1.0."""
    try:
        pnl_score = max(min(pnl_pct / 10.0, 1.0), -1.0)
        time_eff = pnl_pct / max(holding_hours, 0.1)
        time_score = max(min(time_eff / 2.0, 1.0), -1.0)
        risk_adj = pnl_pct / max(volatility, 0.1)
        risk_score = max(min(risk_adj / 3.0, 1.0), -1.0)
        regime_bonus = {"BULL": 0.3, "MILD_BULL": 0.15, "SIDEWAYS": 0.0, "MILD_BEAR": -0.1, "BEAR": -0.2}
        regime_score = max(min(regime_bonus.get(regime, 0.0) + pnl_score * 0.5, 1.0), -1.0)
        w = ML_SCORE_WEIGHTS
        total = w["pnl"]*pnl_score + w["time_efficiency"]*time_score + w["risk_adjusted"]*risk_score + w["regime_fit"]*regime_score
        return round(max(min(total, 1.0), -1.0), 4)
    except Exception:
        return 0.0


def build_trade_features(ticker, action, entry_price, exit_price, pnl_pct,
                         holding_hours, regime, entry_score, candles_df=None,
                         entry_context=None):
    """매매 피처 추출 + JSONL 로깅 — ML 학습 데이터 수집.

    entry_context: capture_entry_context()가 매수 시 캡처한 스냅샷.
    candles_df: 청산 시점 기술적 지표 추출용.
    """
    features = {
        "timestamp": utc_now().isoformat(),
        "ticker": ticker, "action": action,
        "entry_price": entry_price, "exit_price": exit_price,
        "pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
        "holding_hours": round(holding_hours, 2) if holding_hours is not None else None,
        "regime": regime, "entry_score": entry_score,
    }
    # 진입 시점 피처 (capture_entry_context에서)
    if entry_context:
        features["entry_rsi"] = entry_context.get("entry_rsi")
        features["entry_bb_position"] = entry_context.get("bb_position")
        features["entry_adx"] = entry_context.get("entry_adx")
        features["entry_confidence"] = entry_context.get("entry_confidence")
        features["entry_volume_ratio"] = entry_context.get("volume_ratio")
        features["entry_price_percentile"] = entry_context.get("price_percentile")
        features["entry_btc_change"] = entry_context.get("btc_change_pct")
    # 청산 시점 피처
    if candles_df is not None and len(candles_df) >= 20:
        try:
            c = candles_df["Close"]
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            exit_rsi = float((100 - 100 / (1 + rs)).iloc[-1])
            features["exit_rsi"] = round(exit_rsi, 2) if not np.isnan(exit_rsi) else None
            if entry_context is None:
                features["entry_rsi"] = features["exit_rsi"]  # 폴백
            atr = calc_atr(candles_df)
            vol = float(atr.iloc[-1]) / float(c.iloc[-1]) * 100 if float(c.iloc[-1]) > 0 else 1.0
            features["exit_volatility"] = round(vol, 2)
            features["quality_score"] = compute_trade_quality_score(pnl_pct or 0, holding_hours or 0, vol, regime)
        except Exception:
            pass
    # JSONL 로깅
    try:
        with open(ML_FEATURE_LOG, "a") as f:
            f.write(json.dumps(features, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return features


# ============================================
# 매매 히스토리 (trade_history.json)
# ============================================
def _load_trade_history():
    try:
        if os.path.exists(TRADE_HISTORY_FILE):
            with open(TRADE_HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_trade_history(history):
    with open(TRADE_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def capture_entry_context(ticker, result, regime_info, btc_signal):
    """매수 시점 ML 피처 스냅샷 — 이미 조회된 데이터에서만 계산 (추가 API 호출 없음)."""
    ctx = {
        "entry_rsi": round(result.get("rsi", 0), 1),
        "entry_score": round(result.get("ensemble_score", 0), 1),
        "entry_adx": round(result.get("adx", 0), 1),
        "entry_confidence": round(result.get("confidence", 0), 1),
        "market_regime": regime_info.get("regime", ""),
        "regime_adx": round(regime_info.get("adx", 0), 1),
        "regime_vol": round(regime_info.get("vol_20", 0), 1),
    }
    # BB 위치: 현재가가 BB 상단/하단 대비 어디인지 (0=하단, 1=상단)
    bb_upper = result.get("bb_upper", 0)
    bb_lower = result.get("bb_lower", 0)
    if bb_upper > bb_lower:
        ctx["bb_position"] = round((result.get("price", 0) - bb_lower) / (bb_upper - bb_lower), 3)
    else:
        ctx["bb_position"] = 0.5
    # 가격 백분위 (전체 캔들 대비 현재 위치)
    ctx["price_percentile"] = round(result.get("full_percentile", 50), 1)
    # 거래량 비율
    ctx["volume_ratio"] = round(result.get("volume_ratio", 1.0), 1)
    # BTC 24h 변화율
    if btc_signal is not None and len(btc_signal) >= 24:
        btc_now = float(btc_signal["Close"].iloc[-1])
        btc_24h = float(btc_signal["Close"].iloc[-24])
        ctx["btc_change_pct"] = round((btc_now / btc_24h - 1) * 100, 2) if btc_24h > 0 else 0
    else:
        ctx["btc_change_pct"] = 0
    return ctx


def record_trade(ticker, side, price, volume, krw_amount, reason="", entry_price=0, pnl_pct=0, entry_context=None):
    """매매 히스토리 기록. side='BUY'|'SELL'|'PARTIAL_SELL'"""
    history = _load_trade_history()
    record = {
        "timestamp": utc_now().isoformat(),
        "ticker": ticker,
        "side": side,
        "price": round(price, 2),
        "volume": round(volume, 8),
        "krw_amount": round(krw_amount),
        "reason": reason,
    }
    if side in ("SELL", "PARTIAL_SELL"):
        record["entry_price"] = round(entry_price, 2)
        record["pnl_pct"] = round(pnl_pct, 2)
    if entry_context:
        record["entry_context"] = entry_context
    history.append(record)
    _save_trade_history(history)


def _send_trade_analysis_webhook(ticker, side, price, volume, krw_amount, reason, entry_price, pnl_pct, extra_data=None):
    """매도 체결 시 오케스트레이터에 분석 webhook 발송 (비동기, 실패 시 로그 출력)."""
    if not ORCHESTRATOR_URL:
        return  # 환경변수 미설정 시 무시 (GitHub Actions 등)
    try:
        import threading
        def _send():
            try:
                payload = {
                    "ticker": ticker,
                    "side": side,
                    "price": round(price, 2),
                    "volume": round(volume, 8),
                    "krw_amount": round(krw_amount),
                    "reason": reason,
                    "entry_price": round(entry_price, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "timestamp": utc_now().isoformat(),
                }
                if extra_data:
                    payload.update(extra_data)
                url = f"{ORCHESTRATOR_URL}/api/v1/projects/coin-alert/trade-analysis"
                resp = requests.post(url, json=payload, timeout=5)
                if resp.status_code == 200:
                    print(f"   📊 {ticker.replace('KRW-','')} 매매 분석 webhook 전송 완료")
                else:
                    print(f"   ⚠️ {ticker.replace('KRW-','')} webhook 응답 {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                print(f"   ⚠️ {ticker.replace('KRW-','')} webhook 전송 실패: {e}")
        threading.Thread(target=_send, daemon=True).start()
    except Exception as e:
        print(f"   ⚠️ webhook 스레드 생성 실패: {e}")


# ============================================
# Upbit 자동매매
# ============================================
_upbit_client = None


def get_upbit():
    global _upbit_client
    if _upbit_client is None and AUTO_TRADE_ENABLED:
        try:
            _upbit_client = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
            print("   ✅ Upbit 연결 성공")
        except Exception as e:
            print(f"   ❌ Upbit 연결 실패: {e}")
    return _upbit_client


def execute_buy(ticker, krw_amount):
    """시장가 매수 (KRW 금액 기반)"""
    if TRADING_HALT:
        print(f"   🚫 TRADING_HALT 활성 — {ticker} 매수 차단됨")
        return None
    upbit = get_upbit()
    if not upbit:
        return None
    try:
        resp = upbit.buy_market_order(ticker, krw_amount)
        if resp and resp.get("uuid"):
            print(f"   ✅ 매수 주문 접수: {ticker} ₩{krw_amount:,.0f} (uuid: {resp['uuid'][:8]}...)")
            return resp
        else:
            print(f"   ❌ 매수 주문 실패: {ticker} — {resp}")
            return None
    except Exception as e:
        print(f"   ❌ 매수 주문 오류: {ticker} — {e}")
        return None


def execute_sell(ticker, volume):
    """시장가 매도 (코인 수량 기반)"""
    upbit = get_upbit()
    if not upbit:
        return None
    try:
        resp = upbit.sell_market_order(ticker, volume)
        if resp and resp.get("uuid"):
            print(f"   ✅ 매도 주문 접수: {ticker} {volume} (uuid: {resp['uuid'][:8]}...)")
            return resp
        else:
            print(f"   ❌ 매도 주문 실패: {ticker} — {resp}")
            return None
    except Exception as e:
        print(f"   ❌ 매도 주문 오류: {ticker} — {e}")
        return None


def sync_portfolio_with_upbit(portfolio):
    """pyupbit.get_balances()로 실계좌와 포트폴리오 동기화"""
    if not AUTO_TRADE_ENABLED:
        return load_portfolio()
    upbit = get_upbit()
    if not upbit:
        return load_portfolio()
    print("🔄 실계좌 잔고 동기화 중...")
    try:
        balances = upbit.get_balances()
        actual = {}
        for b in balances:
            currency = b.get("currency", "")
            ticker = f"KRW-{currency}"
            volume = float(b.get("balance", 0)) + float(b.get("locked", 0))
            avg_price = float(b.get("avg_buy_price", 0))
            # v5.2: TICKERS + 포트폴리오 보유 종목 모두 동기화 (고아 포지션 포함)
            if (ticker in TICKERS or ticker in portfolio) and volume > 0:
                actual[ticker] = {
                    "volume": volume,
                    "entry_price": avg_price,
                    "entry_date": "synced",
                }
        local = load_portfolio()
        # high_watermark, trailing_stop 보존
        for t in actual:
            if t in local:
                for key in ("entry_date", "partial_taken", "dca_count", "full_position_krw", "tp_level", "high_pnl", "sl_partial_done"):
                    if key in local[t]:
                        actual[t][key] = local[t][key]
            if "dca_count" not in actual[t]:
                actual[t]["dca_count"] = 0
        # _meta, _sell_memory 보존
        if "_meta" in local:
            actual["_meta"] = local["_meta"]
        if "_sell_memory" in local:
            actual["_sell_memory"] = local["_sell_memory"]

        local_set = {k for k in local if k not in ("_meta", "_sell_memory")}
        actual_set = set(actual.keys()) - {"_meta", "_sell_memory"}
        if actual_set != local_set:
            diff = f"로컬{sorted(local_set)} → 실계좌{sorted(actual_set)}"
            print(f"   ⚠️ 불일치 감지: {diff}")
            send_telegram(f"⚠️ 포트폴리오 동기화: {diff}")
        else:
            holdings = sorted(actual_set) if actual_set else ["보유 없음"]
            print(f"   ✅ 동기화 완료: {holdings}")
        save_portfolio(actual)
        return actual
    except Exception as e:
        print(f"   ⚠️ 동기화 실패 (로컬 파일 사용): {e}")
        return load_portfolio()


def fetch_actual_capital():
    """pyupbit.get_balance("KRW")로 현금 잔고 조회"""
    if not AUTO_TRADE_ENABLED:
        return INITIAL_CAPITAL
    upbit = get_upbit()
    if not upbit:
        return INITIAL_CAPITAL
    try:
        krw = upbit.get_balance("KRW")
        if krw and krw > 0:
            print(f"   💰 실계좌 가용 KRW: ₩{krw:,.0f}")
            return krw
    except Exception as e:
        print(f"   ⚠️ 잔고 조회 실패 (기본값 ₩{INITIAL_CAPITAL:,} 사용): {e}")
    return INITIAL_CAPITAL


# ============================================
# 서킷브레이커
# ============================================
def check_circuit_breaker(portfolio, capital, results, mutate_meta=True):
    """포트폴리오 MDD 10% 또는 일일 낙폭 5% 이상 시 매매 중단
    mutate_meta=False: 알림 모드에서 _meta 오염 방지 (계산만, 저장 안 함)"""
    meta = portfolio.get("_meta", {}).copy() if not mutate_meta else portfolio.get("_meta", {})
    current_value = capital
    priced_tickers = set()
    for r in results:
        ticker = r["ticker"]
        if r["signal"] != "NO_DATA" and ticker in portfolio and ticker not in ("_meta", "_sell_memory"):
            pos = portfolio[ticker]
            current_value += r["price"] * pos.get("volume", 0)
            priced_tickers.add(ticker)
    for ticker in portfolio:
        if ticker not in ("_meta", "_sell_memory") and ticker not in priced_tickers:
            pos = portfolio[ticker]
            current_value += pos.get("entry_price", 0) * pos.get("volume", 0)
    peak_value = meta.get("peak_value", current_value)
    if current_value > peak_value:
        meta["peak_value"] = current_value
        meta["peak_date"] = utc_now().strftime("%Y-%m-%d")
        peak_value = current_value
    drawdown = (peak_value - current_value) / peak_value if peak_value > 0 else 0

    # v2.1: 일일 낙폭 체크 (KST 기준 — Upbit 한국 거래일 기준)
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    daily_start_date = meta.get("daily_start_date", "")
    if daily_start_date != today_str:
        meta["daily_start_value"] = current_value
        meta["daily_start_date"] = today_str
    daily_start = meta.get("daily_start_value", current_value)
    daily_dd = (daily_start - current_value) / daily_start if daily_start > 0 else 0

    if mutate_meta:
        meta["version"] = "5.49"
        meta["last_value"] = round(current_value, 0)
        meta["last_check"] = utc_now().strftime("%Y-%m-%d %H:%M")
        meta["daily_dd"] = round(daily_dd, 4)
        portfolio["_meta"] = meta

    if drawdown >= CIRCUIT_BREAKER_DD:
        return True, drawdown, peak_value, "MDD"
    if daily_dd >= DAILY_DD_LIMIT:
        return True, daily_dd, daily_start, "DAILY"
    return False, drawdown, peak_value, "OK"


# ============================================
# 상관관계 기반 노출 패널티
# ============================================
def calc_correlation_penalty(tickers_in_portfolio, all_price_data):
    if len(tickers_in_portfolio) < 2:
        return 1.0
    returns = pd.DataFrame()
    for ticker in tickers_in_portfolio:
        if ticker in all_price_data and len(all_price_data[ticker]) > 0:
            close = all_price_data[ticker]["Close"]
            returns[ticker] = close.pct_change().dropna()
    if len(returns.columns) < 2:
        return 1.0
    corr_matrix = returns.tail(60).corr()
    n = len(corr_matrix)
    total_corr = 0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            val = corr_matrix.iloc[i, j]
            if pd.notna(val):
                total_corr += abs(val)
                count += 1
    avg_corr = total_corr / count if count > 0 else 0
    penalty = 1.0 + avg_corr * 0.5
    return penalty


# ============================================
# 공포탐욕 지수 (코인 전용: alternative.me)
# ============================================
def get_crypto_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        if r.status_code == 200:
            d = r.json()["data"][0]
            return {"score": int(d["value"]), "rating": d["value_classification"]}
    except Exception as e:
        print(f"⚠️ 코인 공포탐욕 조회 실패: {e}")
    return None


def format_fear_greed(fg):
    if not fg:
        return "❓ 조회 실패"
    s = fg["score"]
    if s <= 25:  return f"😱 {s}/100 (극도의 공포)"
    elif s <= 45: return f"😰 {s}/100 (공포)"
    elif s <= 55: return f"😐 {s}/100 (중립)"
    elif s <= 75: return f"😀 {s}/100 (탐욕)"
    else:         return f"🤑 {s}/100 (극도의 탐욕)"


# ============================================
# 데이터 조회 (pyupbit)
# ============================================
def get_upbit_ohlcv(ticker, interval=SIGNAL_INTERVAL, count=SIGNAL_CANDLES):
    """pyupbit로 OHLCV 조회. DataFrame(Open/High/Low/Close/Volume) 반환."""
    for attempt in range(3):
        try:
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
            if df is not None and len(df) >= 10:
                df.columns = [c.capitalize() for c in df.columns]
                df.index = pd.to_datetime(df.index)
                return df.dropna()
        except Exception as e:
            if attempt < 2:
                time.sleep(0.5)
            else:
                print(f"   ⚠️ {ticker} 데이터 조회 실패: {e}")
    return None


def fetch_all_data():
    """전 종목 신호용(1H) + 백테스트용(일봉) 데이터 조회"""
    signal_data = {}
    bt_data = {}
    for ticker in TICKERS:
        df_signal = get_upbit_ohlcv(ticker, SIGNAL_INTERVAL, SIGNAL_CANDLES)
        if df_signal is not None:
            signal_data[ticker] = df_signal
        time.sleep(0.12)  # rate limit 준수
        df_bt = get_upbit_ohlcv(ticker, BT_INTERVAL, BT_CANDLES)
        if df_bt is not None:
            bt_data[ticker] = df_bt
        time.sleep(0.12)
    print(f"   ✅ 신호 데이터: {len(signal_data)}/{len(TICKERS)}종목")
    print(f"   ✅ 백테스트 데이터: {len(bt_data)}/{len(TICKERS)}종목")
    return signal_data, bt_data


# ============================================
# 기술적 지표
# ============================================
def calc_rsi(series, period=RSI_PERIOD):
    d = series.diff()
    g = d.where(d > 0, 0).rolling(period).mean()
    l_val = (-d.where(d < 0, 0)).rolling(period).mean()
    return 100 - (100 / (1 + g / l_val))


def calc_macd(series, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL):
    ef = series.ewm(span=fast, adjust=False).mean()
    es = series.ewm(span=slow, adjust=False).mean()
    ml = ef - es
    sl = ml.ewm(span=signal, adjust=False).mean()
    return ml, sl, ml - sl


def calc_bollinger(series, period=BB_PERIOD, std=BB_STD):
    sma = series.rolling(period).mean()
    sd = series.rolling(period).std()
    return sma + sd * std, sma, sma - sd * std


def calc_adx(data, period=ADX_PERIOD):
    h, l_val, c = data["High"], data["Low"], data["Close"]
    tr = pd.concat([h - l_val, abs(h - c.shift(1)), abs(l_val - c.shift(1))], axis=1).max(axis=1)
    um = h - h.shift(1)
    dm_val = l_val.shift(1) - l_val
    pdm = pd.Series(0.0, index=data.index)
    ndm = pd.Series(0.0, index=data.index)
    pdm[(um > dm_val) & (um > 0)] = um[(um > dm_val) & (um > 0)]
    ndm[(dm_val > um) & (dm_val > 0)] = dm_val[(dm_val > um) & (dm_val > 0)]
    atr = tr.rolling(period).mean()
    pdi = 100 * pdm.rolling(period).mean() / atr
    ndi = 100 * ndm.rolling(period).mean() / atr
    dx = 100 * abs(pdi - ndi) / (pdi + ndi)
    return dx.rolling(period).mean(), pdi, ndi


def calc_atr(data, period=ATR_PERIOD):
    h, l_val, c = data["High"], data["Low"], data["Close"]
    tr = pd.concat([h - l_val, abs(h - c.shift(1)), abs(l_val - c.shift(1))], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_vwap(data):
    """24시간 VWAP 계산 (1시간봉 기준, 최근 24개 캔들)"""
    recent = data.tail(24)
    if len(recent) < 5 or "Volume" not in recent.columns:
        return None
    tp = (recent["High"] + recent["Low"] + recent["Close"]) / 3
    vol = recent["Volume"]
    cum_tpv = (tp * vol).sum()
    cum_vol = vol.sum()
    if cum_vol <= 0:
        return None
    return cum_tpv / cum_vol


# ============================================
# v3.0: 모멘텀 예측 지표 (거래량+히스토리 기반)
# ============================================
def calc_obv(data):
    """OBV (On-Balance Volume) — Granville 1963"""
    direction = np.sign(data["Close"].diff())
    return (data["Volume"] * direction).cumsum()


def calc_mfi(data, period=14):
    """MFI (Money Flow Index) — 거래량 가중 RSI (Quong & Satchell 1997)"""
    tp = (data["High"] + data["Low"] + data["Close"]) / 3
    mf = tp * data["Volume"]
    delta = tp.diff()
    pos_mf = mf.where(delta > 0, 0).rolling(period).sum()
    neg_mf = mf.where(delta <= 0, 0).rolling(period).sum()
    return 100 - (100 / (1 + pos_mf / neg_mf.replace(0, 1e-10)))


def calc_vpt(data):
    """VPT (Volume Price Trend) — 누적 거래량 가중 가격 변화"""
    return (data["Volume"] * data["Close"].pct_change()).cumsum()


def calc_adl(data):
    """ADL (Accumulation/Distribution Line) — 스마트머니 감지"""
    hl_range = (data["High"] - data["Low"]).replace(0, 1e-10)
    clv = ((data["Close"] - data["Low"]) - (data["High"] - data["Close"])) / hl_range
    return (clv * data["Volume"]).cumsum()


def calc_stochastic(data, k_period=5, d_period=3):
    """Stochastic %K/%D — 단기 모멘텀 확인"""
    low_min = data["Low"].rolling(k_period).min()
    high_max = data["High"].rolling(k_period).max()
    denom = (high_max - low_min).replace(0, 1e-10)
    k = 100 * (data["Close"] - low_min) / denom
    d = k.rolling(d_period).mean()
    return k, d


def calc_vwma(data, period=20):
    """VWMA (Volume Weighted Moving Average)"""
    return (data["Close"] * data["Volume"]).rolling(period).sum() / data["Volume"].rolling(period).sum()


def strategy_momentum_prediction(data, today):
    """v3.0: 모멘텀 예측 전략 — 거래량+히스토리 기반 상승 예측 모델

    7개 하위 지표 복합 점수 (-100 ~ +100):
    1. OBV 다이버전스       (±20) — 가격↓+OBV↑ = 강세 다이버전스
    2. MFI                  (±15) — 거래량 가중 RSI, 과매도/과매수
    3. VPT 기울기           (±15) — 누적 거래량 가중 가격 변화 추세
    4. ADL 다이버전스       (±15) — 스마트머니 축적/분배
    5. Stochastic %K/%D     (±10) — 과매도 영역 골든크로스
    6. VWMA 이격도          (±10) — 가격 vs 거래량 가중 이평
    7. MACD 히스토그램 다이버전스 (±15) — 빌딩 모멘텀

    수학적 근거:
    - OBV: Granville 1963 — 거래량은 가격에 선행
    - MFI: Quong & Satchell 1997 — 거래량 가중 RSI
    - VWTSMOM: Huang, Sangiorgi & Urquhart 2024 (Sharpe 2.17)
    """
    score = 0
    close = data["Close"]
    n = len(data)
    if n < 30:
        return 0

    lookback = 14
    # 공통: 가격 기울기 (여러 지표에서 재사용)
    price_slope = 0.0
    if n >= lookback + 1:
        p_end = float(close.iloc[-1])
        p_start = float(close.iloc[-lookback])
        price_slope = (p_end - p_start) / max(abs(p_start), 1e-10)

    # --- 1. OBV 다이버전스 (±20) ---
    obv = calc_obv(data)
    if n >= lookback + 1 and pd.notna(obv.iloc[-1]) and pd.notna(obv.iloc[-lookback]):
        obv_slope = (float(obv.iloc[-1]) - float(obv.iloc[-lookback])) / max(abs(float(obv.iloc[-lookback])), 1e-10)
        if price_slope < -0.01 and obv_slope > 0.01:
            score += 20       # 강세 다이버전스
        elif price_slope > 0.01 and obv_slope < -0.01:
            score -= 20       # 약세 다이버전스
        elif price_slope > 0 and obv_slope > 0:
            score += 8        # 상승 확인
        elif price_slope < 0 and obv_slope < 0:
            score -= 8        # 하락 확인

    # --- 2. MFI (±15) ---
    mfi = calc_mfi(data)
    if pd.notna(mfi.iloc[-1]):
        mfi_val = float(mfi.iloc[-1])
        if mfi_val <= 20:     score += 15   # 과매도
        elif mfi_val <= 30:   score += 8
        elif mfi_val >= 80:   score -= 15   # 과매수
        elif mfi_val >= 70:   score -= 8

    # --- 3. VPT 기울기 (±15) ---
    vpt = calc_vpt(data)
    if n >= lookback + 1 and pd.notna(vpt.iloc[-1]) and pd.notna(vpt.iloc[-lookback]):
        vpt_recent = vpt.iloc[-lookback:].dropna()
        if len(vpt_recent) >= lookback:
            x = np.arange(len(vpt_recent), dtype=float)
            y = vpt_recent.values.astype(float)
            slope = (np.mean(x * y) - np.mean(x) * np.mean(y)) / max(np.var(x), 1e-10)
            avg_vol = float(data["Volume"].tail(lookback).mean())
            norm_slope = slope / max(avg_vol, 1e-10)
            if norm_slope > 0.05:     score += 15
            elif norm_slope > 0.01:   score += 8
            elif norm_slope < -0.05:  score -= 15
            elif norm_slope < -0.01:  score -= 8

    # --- 4. ADL 다이버전스 (±15) ---
    adl = calc_adl(data)
    if n >= lookback + 1 and pd.notna(adl.iloc[-1]) and pd.notna(adl.iloc[-lookback]):
        adl_start = float(adl.iloc[-lookback])
        adl_norm = (float(adl.iloc[-1]) - adl_start) / max(abs(adl_start), 1e-10)
        if price_slope < -0.01 and adl_norm > 0.01:
            score += 15       # 축적 다이버전스
        elif price_slope > 0.01 and adl_norm < -0.01:
            score -= 15       # 분배 다이버전스
        elif adl_norm > 0.02:
            score += 5
        elif adl_norm < -0.02:
            score -= 5

    # --- 5. Stochastic %K/%D (±10) ---
    stoch_k, stoch_d = calc_stochastic(data)
    if n >= 2 and pd.notna(stoch_k.iloc[-1]) and pd.notna(stoch_d.iloc[-1]):
        k_val, d_val = float(stoch_k.iloc[-1]), float(stoch_d.iloc[-1])
        k_prev = float(stoch_k.iloc[-2]) if pd.notna(stoch_k.iloc[-2]) else k_val
        d_prev = float(stoch_d.iloc[-2]) if pd.notna(stoch_d.iloc[-2]) else d_val
        if k_prev <= d_prev and k_val > d_val and k_val < 30:
            score += 10       # 과매도 골든크로스
        elif k_prev >= d_prev and k_val < d_val and k_val > 70:
            score -= 10       # 과매수 데드크로스
        elif k_val > d_val:
            score += 3
        elif k_val < d_val:
            score -= 3

    # --- 6. VWMA 이격도 (±10) ---
    vwma = calc_vwma(data)
    if pd.notna(vwma.iloc[-1]):
        cp = float(close.iloc[-1])
        vwma_val = float(vwma.iloc[-1])
        deviation = (cp - vwma_val) / vwma_val if vwma_val > 0 else 0
        if deviation > 0.02:      score += 10   # VWMA 위 2%+
        elif deviation > 0:       score += 4
        elif deviation < -0.02:   score -= 10   # VWMA 아래 2%+
        elif deviation < 0:       score -= 4

    # --- 7. MACD 히스토그램 다이버전스 (±15) ---
    if "MACD_Hist" in data.columns and n >= 5:
        hist_series = data["MACD_Hist"].tail(5).dropna()
        if len(hist_series) >= 3:
            hist_vals = hist_series.values
            hist_rising = all(hist_vals[i] > hist_vals[i - 1] for i in range(1, len(hist_vals)))
            hist_falling = all(hist_vals[i] < hist_vals[i - 1] for i in range(1, len(hist_vals)))
            price_flat = abs(price_slope) < 0.01
            if hist_rising and price_flat:
                score += 15   # 빌딩 모멘텀
            elif hist_falling and price_flat:
                score -= 15   # 약화 모멘텀
            elif hist_rising:
                score += 7
            elif hist_falling:
                score -= 7

    return max(-100, min(100, score))


def calc_support_resistance(data, lookback=SR_LOOKBACK):
    rec = data.tail(lookback)
    hs, ls = rec["High"].values, rec["Low"].values
    cp = float(data["Close"].iloc[-1])
    last = data.iloc[-1]
    pv = (float(last["High"]) + float(last["Low"]) + float(last["Close"])) / 3
    r1 = 2 * pv - float(last["Low"])
    s1 = 2 * pv - float(last["High"])
    sh, sl_list = [], []
    w = 3
    for i in range(w, len(rec) - w):
        if hs[i] == max(hs[i - w:i + w + 1]):
            sh.append(hs[i])
        if ls[i] == min(ls[i - w:i + w + 1]):
            sl_list.append(ls[i])

    def cluster(lvls, th=0.01):
        if not lvls:
            return []
        lvls = sorted(lvls)
        cl = [[lvls[0]]]
        for v in lvls[1:]:
            if (v - cl[-1][-1]) / cl[-1][-1] < th:
                cl[-1].append(v)
            else:
                cl.append([v])
        return [np.mean(c) for c in cl]

    rl, spl = cluster(sh), cluster(sl_list)
    nr = next((v for v in sorted(rl) if v > cp), r1)
    ns = next((v for v in sorted(spl, reverse=True) if v < cp), s1)
    return {
        "resistance": nr, "support": ns,
        "near_resistance": abs(cp - nr) / cp < SR_PROXIMITY,
        "near_support": abs(cp - ns) / cp < SR_PROXIMITY,
    }


def calc_weekly_signals(data):
    """주봉 대신 일봉 기반 중기 추세 (코인: 주봉 별도 없이 일봉 활용)"""
    if data is None or len(data) < 22:
        return {"trend": "UNKNOWN", "rsi": None, "ma_signal": "UNKNOWN"}
    c = data["Close"]
    ss = c.rolling(10).mean()
    sl = c.rolling(20).mean()
    rsi = calc_rsi(c)
    t, y = {"SS": float(ss.iloc[-1]), "SL": float(sl.iloc[-1]), "RSI": float(rsi.iloc[-1])}, \
           {"SS": float(ss.iloc[-2]), "SL": float(sl.iloc[-2])}
    tr = "UP" if t["SS"] > t["SL"] else "DOWN"
    ma = "HOLD"
    if y["SS"] <= y["SL"] and t["SS"] > t["SL"]:
        ma = "BUY"
    elif y["SS"] >= y["SL"] and t["SS"] < t["SL"]:
        ma = "SELL"
    return {"trend": tr, "rsi": t["RSI"], "ma_signal": ma}


# ============================================
# 시장 레짐 감지 (BTC 기준)
# ============================================
def detect_market_regime(btc_data):
    c = btc_data["Close"]
    s50  = c.rolling(50).mean()
    s200 = c.rolling(200).mean()
    # 코인: 1H봉 기준 변동성 → 연율화 (24*365)
    vol20 = c.pct_change().tail(20).std() * np.sqrt(24 * 365) * 100
    p    = float(c.iloc[-1])
    sv50 = float(s50.iloc[-1])
    sv200 = float(s200.iloc[-1]) if pd.notna(s200.iloc[-1]) else sv50
    adx_s, _, _ = calc_adx(btc_data)
    av = float(adx_s.iloc[-1]) if pd.notna(adx_s.iloc[-1]) else 15
    a50, a200, st = p > sv50, p > sv200, av >= ADX_STRONG_TREND
    # 코인은 변동성이 기본적으로 높으므로 VOLATILE 기준을 높임
    if vol20 > 80 and not st:
        regime = "VOLATILE"
    elif a50 and a200 and st:
        regime = "BULL"
    elif not a50 and not a200 and st:
        regime = "BEAR"
    elif a50 and a200:
        regime = "MILD_BULL"
    elif not a50 and not a200:
        regime = "MILD_BEAR"
    else:
        regime = "SIDEWAYS"
    return {"regime": regime, "adx": av, "vol_20": vol20, "above_sma50": a50, "above_sma200": a200}


def get_regime_emoji(r):
    return {
        "BULL": "🟢 강한 상승장", "MILD_BULL": "🟡 약한 상승장",
        "SIDEWAYS": "⚪ 횡보장", "MILD_BEAR": "🟠 약한 하락장",
        "BEAR": "🔴 강한 하락장", "VOLATILE": "🌪️ 고변동성",
    }.get(r, r)


def get_regime_threshold(r):
    """v4.0: 높은 임계값 — 더 적지만 확실한 신호"""
    return {
        "BULL":      22,
        "MILD_BULL": 20,
        "SIDEWAYS":  18,
        "MILD_BEAR": 20,
        "BEAR":      22,
        "VOLATILE":  20,
    }.get(r, SIGNAL_THRESHOLD)


def get_regime_scoring(r):
    """v5.39: 레짐별 적응형 스코어링 — 시장 상황에 따라 매수/매도 기준 변동.

    하락장: 진짜 바닥에서만 사고, 조금만 올라도 바로 판다
    상승장: 넓게 사고, 추세를 충분히 탄다
    """
    return {
        #                rsi_3pt  rsi_1pt  min_score  sell_trigger  tp1_pct
        "BEAR":         {"rsi_3pt": 20, "rsi_1pt": 30, "min_entry": 7, "sell_trigger": 60, "tp1_pct": 2.0},
        "MILD_BEAR":    {"rsi_3pt": 25, "rsi_1pt": 35, "min_entry": 7, "sell_trigger": 65, "tp1_pct": 2.5},
        "SIDEWAYS":     {"rsi_3pt": 30, "rsi_1pt": 40, "min_entry": 6, "sell_trigger": 70, "tp1_pct": 3.0},
        "MILD_BULL":    {"rsi_3pt": 35, "rsi_1pt": 45, "min_entry": 6, "sell_trigger": 75, "tp1_pct": 3.0},
        "BULL":         {"rsi_3pt": 40, "rsi_1pt": 50, "min_entry": 5, "sell_trigger": 80, "tp1_pct": 4.0},
        "VOLATILE":     {"rsi_3pt": 25, "rsi_1pt": 35, "min_entry": 7, "sell_trigger": 65, "tp1_pct": 2.5},
    }.get(r, {"rsi_3pt": 30, "rsi_1pt": 40, "min_entry": 6, "sell_trigger": 70, "tp1_pct": 3.0})


def get_regime_strategy_weights(r):
    """v4.0: 평균회귀 중심 3-전략 가중치 (breakout 제거)"""
    return {
        "BULL":      {"trend": 0.15, "mean_revert": 0.55, "momentum_pred": 0.30},
        "MILD_BULL": {"trend": 0.10, "mean_revert": 0.60, "momentum_pred": 0.30},
        "SIDEWAYS":  {"trend": 0.05, "mean_revert": 0.65, "momentum_pred": 0.30},
        "MILD_BEAR": {"trend": 0.10, "mean_revert": 0.60, "momentum_pred": 0.30},
        "BEAR":      {"trend": 0.15, "mean_revert": 0.55, "momentum_pred": 0.30},
        "VOLATILE":  {"trend": 0.05, "mean_revert": 0.60, "momentum_pred": 0.35},
    }.get(r, {"trend": 0.10, "mean_revert": 0.60, "momentum_pred": 0.30})


# ============================================
# 멀티 전략 앙상블
# ============================================
def strategy_trend_following(data, today, yesterday):
    """v4.0: 축소된 추세 추종 — 확인 역할만 (주도 아닌 보조)"""
    score = 0
    if yesterday["SMA_Short"] <= yesterday["SMA_Long"] and today["SMA_Short"] > today["SMA_Long"]:
        score += 25    # v4.0: 40→25
    elif yesterday["SMA_Short"] >= yesterday["SMA_Long"] and today["SMA_Short"] < today["SMA_Long"]:
        score -= 25
    elif today["SMA_Short"] > today["SMA_Long"]:
        score += 8     # v4.0: 15→8
    else:
        score -= 8
    if yesterday["MACD"] <= yesterday["MACD_Signal"] and today["MACD"] > today["MACD_Signal"]:
        score += 20    # v4.0: 30→20
    elif yesterday["MACD"] >= yesterday["MACD_Signal"] and today["MACD"] < today["MACD_Signal"]:
        score -= 20
    elif today["MACD_Hist"] > 0:
        score += 5     # v4.0: 10→5
    else:
        score -= 5
    adx_val = float(today["ADX"]) if pd.notna(today.get("ADX")) else 0
    di_sign = 1 if today["Plus_DI"] > today["Minus_DI"] else -1
    if adx_val >= 35:
        score += 20 * di_sign    # v4.0: 30→20
    elif adx_val >= ADX_STRONG_TREND:
        score += 12 * di_sign    # v4.0: 20→12
    elif adx_val >= 15:
        score += 5 * di_sign     # v4.0: 10→5
    return max(-100, min(100, score))


def strategy_mean_reversion(data, today):
    """v4.0: 강화된 평균회귀 — 주도 전략 (55-65% 비중)"""
    score = 0
    rsi = float(today["RSI"])
    p = float(today["Close"])
    # v4.0: RSI 점수 강화 — 더 넓은 범위, 더 강한 점수
    if rsi <= 20:        score += 60     # 극도 과매도
    elif rsi <= 25:      score += 50     # 과매도
    elif rsi <= 30:      score += 40     # 준과매도
    elif rsi <= 40:      score += 20     # 저RSI 구간
    elif rsi <= 50:      score += 5      # 중립-저
    elif rsi >= 80:      score -= 60     # 극도 과매수
    elif rsi >= 70:      score -= 50     # 과매수
    elif rsi >= 65:      score -= 35     # 매도 고려
    elif rsi >= 60:      score -= 20     # 고RSI 진입
    # 볼린저 밴드 (유지)
    bu = float(today["BB_Upper"])
    bl = float(today["BB_Lower"])
    bm = float(today["BB_Mid"])
    if p <= bl:                          score += 40
    elif p <= bm - (bm - bl) * 0.5:     score += 20
    elif p >= bu:                        score -= 40
    elif p >= bm + (bu - bm) * 0.5:     score -= 20
    # 지지/저항
    sr = calc_support_resistance(data)
    if sr["near_support"]:    score += 10
    if sr["near_resistance"]: score -= 10
    return max(-100, min(100, score))


def strategy_breakout(data, today):
    score = 0
    c = data["Close"]
    p = float(today["Close"])
    # 코인: 52주 대신 450캔들(~19일 1H 기준) 고점/저점
    c_all = c
    h_max, l_min = float(c_all.max()), float(c_all.min())
    if p >= h_max * 0.98:
        score += 40
    elif p <= l_min * 1.02:
        score -= 40
    elif len(c) >= 50 and p >= float(c.tail(50).max()) * 0.99:
        score += 25
    elif len(c) >= 50 and p <= float(c.tail(50).min()) * 1.01:
        score -= 25
    elif len(c) >= 20 and p >= float(c.tail(20).max()):
        score += 15
    elif len(c) >= 20 and p <= float(c.tail(20).min()):
        score -= 15
    av = data["Volume"].rolling(20).mean().iloc[-1]
    vr = float(today["Volume"]) / float(av) if float(av) > 0 else 1
    dc = (p / float(data["Close"].iloc[-2]) - 1) * 100
    if vr >= 3:   score += 45 if dc > 0 else -45   # v2.0: 3x 볼륨 부스트
    elif vr >= 2:   score += 30 if dc > 0 else -30
    elif vr >= 1.5: score += 15 if dc > 0 else -15
    if p > float(today["BB_Upper"]): score += 30
    elif p < float(today["BB_Lower"]): score -= 30
    return max(-100, min(100, score))


def ensemble_signal(t, m, b, w, mp=0):
    """v4.0: 3-전략 앙상블 (breakout 제거, 평균회귀 중심)"""
    score = t * w.get("trend", 0.10) + m * w.get("mean_revert", 0.60)
    if "momentum_pred" in w:
        score += mp * w.get("momentum_pred", 0.30)
    return score


# ============================================
# 백테스팅 (일봉 기반 Walk-Forward)
# ============================================
def quick_backtest(data, rw, btc_data=None, return_trades=False):
    c = data["Close"]
    data = data.copy()
    data["SMA_Short"] = c.rolling(SHORT_WINDOW).mean()
    data["SMA_Long"]  = c.rolling(LONG_WINDOW).mean()
    data["RSI"]       = calc_rsi(c)
    data["MACD"], data["MACD_Signal"], data["MACD_Hist"] = calc_macd(c)
    data["BB_Upper"], data["BB_Mid"], data["BB_Lower"]   = calc_bollinger(c)
    data["ADX"], data["Plus_DI"], data["Minus_DI"]       = calc_adx(data)
    data["ATR"] = calc_atr(data)

    cost_pct = TOTAL_COST_BPS / 10000
    trades = []
    pos = None

    for i in range(LONG_WINDOW + 2, len(data) - 1):
        t_bar = data.iloc[i]
        y_bar = data.iloc[i - 1]
        next_open = float(data.iloc[i + 1]["Open"])
        sd = data.iloc[:i + 1]

        current_rw = rw
        current_threshold = SIGNAL_THRESHOLD
        if btc_data is not None:
            bar_date = data.index[i]
            btc_slice = btc_data.loc[:bar_date]
            if len(btc_slice) >= 200:
                try:
                    ri_t = detect_market_regime(btc_slice)
                    current_rw = get_regime_strategy_weights(ri_t["regime"])
                    current_threshold = get_regime_threshold(ri_t["regime"])
                except Exception:
                    pass

        # v4.0: breakout 비활성화, 3-전략 앙상블
        total = ensemble_signal(
            strategy_trend_following(sd, t_bar, y_bar),
            strategy_mean_reversion(sd, t_bar),
            0,  # v4.0: breakout 제거
            current_rw,
            strategy_momentum_prediction(sd, t_bar),
        )

        atr_val = float(t_bar["ATR"]) if pd.notna(t_bar["ATR"]) else 0
        rsi_val = float(t_bar["RSI"]) if pd.notna(t_bar.get("RSI")) else 50

        # v4.0: RSI 매수 차단 필터 (백테스트에도 동일 적용)
        if total > 0 and rsi_val > RSI_BUY_CEILING:
            total = min(total, -5)

        if pos is None:
            if total >= current_threshold:
                entry_price = next_open * (1 + cost_pct)
                pos = {"entry": entry_price, "idx": i + 1, "partial": False, "tp_level": 0, "high_pnl": 0, "sl_partial_done": False}
        else:
            hold_days = i - pos["idx"]
            cp = float(t_bar["Close"])
            pnl_pct = (cp / pos["entry"] - 1) * 100

            # 트레일링 고점 갱신
            pos["high_pnl"] = max(pos.get("high_pnl", 0), pnl_pct)

            # v5.20.1: 3단계 분할 익절 반영
            tp_level = pos.get("tp_level", 0)
            # TP1: 50% 매도
            if pnl_pct >= PROFIT_TARGET_1ST and tp_level < 1:
                partial_pnl = pnl_pct * PARTIAL_SELL_RATIO_1
                trades.append({"pnl": partial_pnl, "days": hold_days, "reason": "PARTIAL_TP1", "entry_idx": pos["idx"]})
                pos["partial"] = True
                pos["tp_level"] = 1
            # TP2: 잔여의 60% 매도 (전체 30%)
            if pnl_pct >= PROFIT_TARGET_2ND and tp_level == 1:
                remaining = 1 - PARTIAL_SELL_RATIO_1  # 60%
                partial_pnl = pnl_pct * remaining * PARTIAL_SELL_RATIO_2
                trades.append({"pnl": partial_pnl, "days": hold_days, "reason": "PARTIAL_TP2", "entry_idx": pos["idx"]})
                pos["tp_level"] = 2

            # v5.31: 매도 우선순위 (손절최소화 대원칙)
            # TP3 → CATASTROPHIC → TIME_STOP → TRAILING → SL → SIGNAL_EXIT
            exit_reason = None
            exit_price  = None
            if pnl_pct >= PROFIT_TARGET_3RD:
                exit_reason = "PROFIT_TARGET"
                exit_price  = cp * (1 - cost_pct)
            elif pnl_pct <= -CATASTROPHIC_STOP_PCT:
                exit_reason = "CATASTROPHIC_STOP"
                exit_price  = cp * (1 - cost_pct)
            elif hold_days >= MAX_HOLD_DAYS:
                exit_reason = "TIME_STOP"
                exit_price  = next_open * (1 - cost_pct)
            elif pos["high_pnl"] >= TRAILING_ACTIVATE_PCT and (pos["high_pnl"] - pnl_pct) >= TRAILING_CALLBACK_PCT:
                exit_reason = "TRAILING_STOP"
                exit_price  = cp * (1 - cost_pct)
            elif tp_level >= 1 and TP1_BREAKEVEN_SL and pnl_pct <= 0:
                exit_reason = "BREAKEVEN_STOP"
                exit_price  = cp * (1 - cost_pct)
            elif PARTIAL_SL_ENABLED and not pos.get("sl_partial_done") and pnl_pct <= -PARTIAL_SL_1ST_PCT:
                # v5.48: 백테스트 분할 손절 1단계 — 50% 매도
                remaining_ratio = 1 - PARTIAL_SELL_RATIO_1 if tp_level == 0 else (1 - PARTIAL_SELL_RATIO_1) * (1 - PARTIAL_SELL_RATIO_2 if tp_level >= 2 else 1)
                partial_pnl = pnl_pct * PARTIAL_SL_RATIO * remaining_ratio
                trades.append({"pnl": partial_pnl, "days": hold_days, "reason": "PARTIAL_SL1", "entry_idx": pos["idx"]})
                pos["sl_partial_done"] = True
            elif PARTIAL_SL_ENABLED and pos.get("sl_partial_done") and pnl_pct <= -PARTIAL_SL_2ND_PCT:
                # v5.48: 백테스트 분할 손절 2단계 — 나머지 전량 매도
                exit_reason = "STOP_LOSS"
                exit_price  = cp * (1 - cost_pct)
            elif not PARTIAL_SL_ENABLED and pnl_pct <= -LOSS_CUT_PCT:
                exit_reason = "STOP_LOSS"
                exit_price  = cp * (1 - cost_pct)
            elif total <= -current_threshold:
                exit_reason = "SIGNAL_EXIT"
                exit_price  = next_open * (1 - cost_pct)

            if exit_reason:
                pnl = (exit_price / pos["entry"] - 1) * 100
                # 분할 익절 단계에 따라 잔여 비율 계산
                tp_lvl = pos.get("tp_level", 0)
                if tp_lvl >= 2:
                    remaining_ratio = (1 - PARTIAL_SELL_RATIO_1) * (1 - PARTIAL_SELL_RATIO_2)  # 30%
                elif tp_lvl >= 1:
                    remaining_ratio = 1 - PARTIAL_SELL_RATIO_1  # 60%
                else:
                    remaining_ratio = 1.0
                trades.append({"pnl": pnl * remaining_ratio, "days": hold_days, "reason": exit_reason, "entry_idx": pos["idx"]})
                pos = None

    if pos:
        exit_price = float(data["Close"].iloc[-1]) * (1 - cost_pct)
        pnl = (exit_price / pos["entry"] - 1) * 100
        trades.append({"pnl": pnl, "days": len(data) - pos["idx"], "reason": "OPEN", "entry_idx": pos["idx"]})

    empty = {
        "win_rate": DEFAULT_WIN_RATE, "wl_ratio": DEFAULT_WIN_LOSS_RATIO,
        "total_trades": 0, "avg_pnl": 0, "use_kelly": False,
        "sharpe": 0, "max_dd": 0, "calmar": 0, "total_return": 0,
    }
    if not trades:
        return empty

    wins   = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    wr = len(wins) / len(trades)
    aw = np.mean([t["pnl"] for t in wins])   if wins   else 1
    al = abs(np.mean([t["pnl"] for t in losses])) if losses else 1
    use_kelly = len(trades) >= MIN_TRADES_FOR_KELLY

    pnl_series  = pd.Series([t["pnl"] for t in trades])
    avg_holding = np.mean([t["days"] for t in trades])
    trades_per_year = 365 / avg_holding if avg_holding > 0 else 12
    sharpe = (pnl_series.mean() / pnl_series.std() * np.sqrt(trades_per_year)
              if pnl_series.std() > 0 else 0)
    cumulative  = (1 + pnl_series / 100).cumprod()
    peak        = cumulative.cummax()
    drawdown    = (cumulative - peak) / peak
    max_dd      = float(drawdown.min()) * 100
    total_return = float((cumulative.iloc[-1] - 1) * 100)
    total_days  = sum(t["days"] for t in trades)
    annual_return = total_return * (365 / total_days) if total_days > 0 else 0
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

    result = {
        "win_rate": wr, "wl_ratio": aw / al if al > 0 else DEFAULT_WIN_LOSS_RATIO,
        "total_trades": len(trades), "wins": len(wins), "losses": len(losses),
        "avg_pnl": np.mean([t["pnl"] for t in trades]),
        "avg_win": aw if wins else 0, "avg_loss": al if losses else 0,
        "use_kelly": use_kelly, "sharpe": round(sharpe, 2),
        "max_dd": round(max_dd, 1), "calmar": round(calmar, 2),
        "total_return": round(total_return, 1),
    }
    if return_trades:
        result["_trades"] = trades
    return result


def walk_forward_backtest(data, rw, btc_data=None):
    """Walk-forward out-of-sample 백테스트. 150일 train + 50일 test."""
    total_bars = len(data)
    train_bars = 150
    test_bars  = 50
    min_required = train_bars + test_bars

    if total_bars < min_required:
        return quick_backtest(data, rw, btc_data)

    n_windows = max(1, (total_bars - train_bars) // test_bars)
    all_test_trades = []

    for w in range(n_windows):
        window_start = w * test_bars
        window_end   = min(window_start + train_bars + test_bars, total_bars)
        window_data  = data.iloc[window_start:window_end].copy()

        bt_slice = btc_data.iloc[window_start:window_end].copy() if btc_data is not None else None
        wf_bt = quick_backtest(window_data, rw, bt_slice, return_trades=True)
        test_trades = [t for t in wf_bt.get("_trades", []) if t["entry_idx"] >= train_bars]
        all_test_trades.extend(test_trades)

    if not all_test_trades:
        return quick_backtest(data, rw, btc_data)

    wins   = [t for t in all_test_trades if t["pnl"] > 0]
    losses = [t for t in all_test_trades if t["pnl"] <= 0]
    wr = len(wins) / len(all_test_trades)
    aw = np.mean([t["pnl"] for t in wins])   if wins   else 1
    al = abs(np.mean([t["pnl"] for t in losses])) if losses else 1
    pnl_series  = pd.Series([t["pnl"] for t in all_test_trades])
    avg_holding = np.mean([t["days"] for t in all_test_trades])
    trades_per_year = 365 / avg_holding if avg_holding > 0 else 12
    sharpe = (pnl_series.mean() / pnl_series.std() * np.sqrt(trades_per_year)
              if pnl_series.std() > 0 else 0)
    cumulative = (1 + pnl_series / 100).cumprod()
    peak       = cumulative.cummax()
    max_dd     = float(((cumulative - peak) / peak).min()) * 100
    total_return = float((cumulative.iloc[-1] - 1) * 100)
    total_days   = sum(t["days"] for t in all_test_trades)
    annual_return = total_return * (365 / total_days) if total_days > 0 else 0
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

    return {
        "win_rate": wr, "wl_ratio": aw / al if al > 0 else DEFAULT_WIN_LOSS_RATIO,
        "total_trades": len(all_test_trades), "wins": len(wins), "losses": len(losses),
        "avg_pnl": float(pnl_series.mean()),
        "avg_win": aw if wins else 0, "avg_loss": al if losses else 0,
        "use_kelly": len(all_test_trades) >= MIN_TRADES_FOR_KELLY,
        "sharpe": round(sharpe, 2), "max_dd": round(max_dd, 1),
        "calmar": round(calmar, 2), "total_return": round(total_return, 1),
    }


# ============================================
# 포지션 사이징 (inverse-ATR 기반)
# ============================================
def calc_position_size(atr_val, price, conf, bt, capital=INITIAL_CAPITAL):
    """v4.0: 집중 포지션 사이징 (종목당 ~30%, 신뢰도 스케일)"""
    if price <= 0 or atr_val <= 0:
        return {"position_pct": 0, "position_krw": 0, "method": "SKIP", "kelly_ref": 0}
    if conf < 25:  # v4.0: 최소 신뢰도 25
        return {"position_pct": 0, "position_krw": 0, "method": "SKIP", "kelly_ref": 0}
    if bt.get("total_trades", 0) >= 10 and bt.get("sharpe", 0) < -0.5:
        return {"position_pct": 0, "position_krw": 0, "method": "BT_REJECT", "kelly_ref": 0}

    # v4.0: 기본 12% 포지션, 신뢰도에 따라 50~100% 스케일
    base_pct = 0.12
    conf_mult = max(0.5, min(1.0, conf / 80))  # conf 40→0.5, conf 80→1.0
    position_pct = base_pct * conf_mult
    position_pct = max(MIN_POSITION_PCT, min(MAX_POSITION_PCT, position_pct))

    kelly_ref = 0
    if bt.get("use_kelly"):
        wr, wlr = bt["win_rate"], bt["wl_ratio"]
        kelly_ref = max(0, wr - (1 - wr) / wlr) * KELLY_FRACTION if wlr > 0 else 0

    return {
        "position_pct": position_pct * 100,
        "position_krw": capital * position_pct,
        "method": "CONCENTRATED",
        "kelly_ref": round(kelly_ref * 100, 1),
        "atr_pct": round(atr_val / price * 100, 2),
    }


# ============================================
# 종합 분석
# ============================================
def analyze_ticker(ticker, data, regime_info, regime_weights, fear_greed,
                   btc_data=None, backtest_data=None, capital=INITIAL_CAPITAL):
    if len(data) < LONG_WINDOW + 2:
        return {"ticker": ticker, "signal": "NO_DATA"}

    c = data["Close"]
    data = data.copy()
    data["SMA_Short"] = c.rolling(SHORT_WINDOW).mean()
    data["SMA_Long"]  = c.rolling(LONG_WINDOW).mean()
    data["RSI"]       = calc_rsi(c)
    data["MACD"], data["MACD_Signal"], data["MACD_Hist"] = calc_macd(c)
    data["BB_Upper"], data["BB_Mid"], data["BB_Lower"]   = calc_bollinger(c)
    data["ADX"], data["Plus_DI"], data["Minus_DI"]       = calc_adx(data)
    data["ATR"] = calc_atr(data)

    t, y = data.iloc[-1], data.iloc[-2]
    cp  = float(t["Close"])
    dc  = (cp / float(y["Close"]) - 1) * 100
    rsi = float(t["RSI"])
    rs  = "과매수 ⚠️" if rsi >= RSI_OVERBOUGHT else "과매도 🔥" if rsi <= RSI_OVERSOLD else "중립"
    bs  = "상단 돌파 ⚠️" if cp >= float(t["BB_Upper"]) else "하단 이탈 🔥" if cp <= float(t["BB_Lower"]) else "밴드 내"
    adx   = float(t["ADX"]) if pd.notna(t["ADX"]) else 0
    pdi   = float(t["Plus_DI"]) if pd.notna(t["Plus_DI"]) else 0
    ndi   = float(t["Minus_DI"]) if pd.notna(t["Minus_DI"]) else 0
    atr_val = float(t["ATR"]) if pd.notna(t["ATR"]) else 0
    av    = data["Volume"].rolling(20).mean().iloc[-1]
    vr    = float(t["Volume"]) / float(av) if float(av) > 0 else 0
    sr    = calc_support_resistance(data)

    # v5.9: 24h ê±°ëëê¸ Upbit API (candle fallback)
    vol_24h = _get_24h_trade_value(ticker)
    if vol_24h is None:
        vol_24h = (data["Volume"].tail(24) * data["Close"].tail(24)).sum()

    ts  = strategy_trend_following(data, t, y)
    ms  = strategy_mean_reversion(data, t)
    bks = 0  # v4.0: breakout 전략 비활성화 (고점 매수 원인)
    mps = strategy_momentum_prediction(data, t)
    es  = ensemble_signal(ts, ms, bks, regime_weights, mps)

    # v4.0: 거래량 급증 보너스 (breakout에서 추출한 유용한 부분)
    vr_bonus = float(t["Volume"]) / float(data["Volume"].rolling(20).mean().iloc[-1]) if float(data["Volume"].rolling(20).mean().iloc[-1]) > 0 else 1
    if vr_bonus >= 2.0:
        es *= 1.15  # 거래량 급증 시 신호 15% 부스트

    # v4.0: VWAP 필터 (유지, 약간 완화)
    vwap = calc_vwap(data)
    if vwap is not None:
        if es > 0 and cp < vwap:
            es *= 0.8   # v4.0: 0.7→0.8 완화
        elif es < 0 and cp > vwap:
            es *= 0.8

    # v4.0: 하드 RSI 매수 차단 필터 (비타협)
    if es > 0 and rsi > RSI_BUY_CEILING:
        es = min(es, -5)  # 매수 불가 영역으로 강제 이동

    # v5.39: 레짐별 적응형 진입 스코어링 (시장 상황에 따라 기준 변동)
    regime_scoring = get_regime_scoring(regime_info["regime"])
    entry_score = 0
    full_percentile = 50.0  # 기본값 (es <= 0일 때도 반환 dict에 포함)
    if es > 0:  # 매수 신호일 때만 스코어링
        # RSI 과매도 가산 (최대 3점) — 레짐별 기준 적용
        rsi_3pt = regime_scoring["rsi_3pt"]  # BEAR:20, SIDEWAYS:30, BULL:40
        rsi_1pt = regime_scoring["rsi_1pt"]  # BEAR:30, SIDEWAYS:40, BULL:50
        if rsi <= rsi_3pt:              entry_score += 3  # 레짐별 명확한 과매도
        elif rsi <= rsi_1pt:            entry_score += 1  # 레짐별 약한 과매도
        # BB 하단 근접 가산 (최대 2점)
        bb_lower = float(t["BB_Lower"]) if pd.notna(t.get("BB_Lower")) else cp
        if cp <= bb_lower:              entry_score += 2  # BB 하단 이탈
        elif cp <= bb_lower * 1.01:     entry_score += 1  # BB 하단 1% 이내
        # ADX 약추세 가산 (1점) — 평균회귀에 유리
        if adx < 25:                    entry_score += 1
        # 지지선 근접 가산 (1점)
        if sr.get("near_support"):      entry_score += 1
        # 거래량 급증 가산 (1점)
        if vr >= 1.5:                   entry_score += 1
        # 24h 가격위치 감점 (대원칙3 "추격매수 절대 금지")
        h24 = data["High"].tail(24).max()
        l24 = data["Low"].tail(24).min()
        if h24 > l24:
            percentile = (cp - l24) / (h24 - l24) * 100
            if percentile >= PRICE_PERCENTILE_BLOCK:
                entry_score -= PRICE_PERCENTILE_PENALTY  # 고점 구간 -3점

        # v5.50: 최저가 기준 거리 매수 필터 (최저가 대비 몇% 위인지)
        full_low = float(data["Low"].min())
        if full_low > 0:
            full_percentile = (cp / full_low - 1) * 100  # 최저가 대비 거리%
            regime_dist_max = ENTRY_LOW_DISTANCE_MAX.get(regime_info["regime"], 5)
            if full_percentile > regime_dist_max:
                es = 0  # 매수 신호 무효화
                name = ticker.replace("KRW-", "")
                print(f"   🚫 {name} 최저가 거리 필터: +{full_percentile:.1f}% > {regime_dist_max}% ({regime_info['regime']})")

        # 스코어 미달 시 매수 차단 — 레짐별 기준 적용
        regime_min_entry = regime_scoring["min_entry"]  # BEAR:7, SIDEWAYS:6, BULL:5
        if entry_score < regime_min_entry:
            es = 0  # 매수 신호 무효화 → HOLD

    threshold = get_regime_threshold(regime_info["regime"])

    if es >= 50:         sig = "STRONG_BUY"
    elif es >= threshold: sig = "BUY"
    elif es <= -50:       sig = "STRONG_CLOSE"
    elif es <= -threshold: sig = "CLOSE"
    else:                  sig = "HOLD"

    bt_src = backtest_data if backtest_data is not None else data.copy()
    bt = walk_forward_backtest(bt_src, regime_weights, btc_data)

    wk = calc_weekly_signals(backtest_data)

    if abs(es) >= threshold:
        conf = min(100, 40 + (abs(es) - threshold) * 2)
    else:
        conf = max(0, abs(es) * 40 / threshold) if threshold > 0 else 0
    if bt.get("total_trades", 0) >= 5:
        bt_sharpe = bt.get("sharpe", 0)
        if bt_sharpe >= 1.5:  conf = min(100, conf + 15)
        elif bt_sharpe >= 0.5: conf = min(100, conf + 10)
        if bt.get("win_rate", 0) > 0.50: conf = min(100, conf + 10)
    if wk["trend"] != "UNKNOWN":
        if (es > 0 and wk["trend"] == "UP") or (es < 0 and wk["trend"] == "DOWN"):
            conf = min(100, conf + 10)
        else:
            conf = max(0, conf - 10)
    if fear_greed:
        fg = fear_greed["score"]
        if (es > 0 and fg <= 30) or (es < 0 and fg >= 70):
            conf = min(100, conf + 5)

    conf = round(conf)  # v3.0: 정수 변환

    stop_loss   = cp - atr_val * ATR_STOP_MULT   if atr_val > 0 else cp * 0.92
    take_profit = cp + atr_val * ATR_TARGET_MULT  if atr_val > 0 else cp * 1.15

    ps = calc_position_size(atr_val, cp, conf, bt, capital=capital)

    # v2.0: 공포탐욕 지수 기반 포지션 사이즈 조정 + v2.1: 재클램프
    if fear_greed and ps["position_pct"] > 0:
        fg_score = fear_greed["score"]
        if fg_score <= 25:       # 극도 공포 → 매수 기회, 사이즈 확대
            fg_mult = 1.3
        elif fg_score >= 75:     # 극도 탐욕 → 리스크 축소
            fg_mult = 0.6
        else:
            fg_mult = 1.0
        if fg_mult != 1.0:
            ps["position_pct"] *= fg_mult
            ps["position_krw"] *= fg_mult
            ps["fg_mult"] = fg_mult
            # v2.1: fg_mult 적용 후 MAX_POSITION_PCT 재클램프
            max_pct = MAX_POSITION_PCT * 100
            if ps["position_pct"] > max_pct:
                ps["position_krw"] *= max_pct / ps["position_pct"]
                ps["position_pct"] = max_pct

    return {
        "ticker": ticker, "signal": sig, "price": cp, "daily_change": dc,
        "sma_short": float(t["SMA_Short"]) if pd.notna(t["SMA_Short"]) else cp,
        "sma_long":  float(t["SMA_Long"])  if pd.notna(t["SMA_Long"]) else cp,
        "rsi": rsi, "rsi_status": rs, "macd_hist": float(t["MACD_Hist"]),
        "bb_status": bs, "bb_upper": float(t["BB_Upper"]), "bb_lower": float(t["BB_Lower"]),
        "adx": adx, "adx_trend": "상승" if pdi > ndi else "하락",
        "atr": atr_val, "stop_loss": stop_loss, "take_profit": take_profit,
        "volume_ratio": vr, "volume_spike": vr >= VOLUME_SPIKE_RATIO,
        "price_high": float(c.max()), "price_low": float(c.min()),
        "is_surge": abs(dc) >= PRICE_CHANGE_THRESHOLD,
        "support": sr["support"], "resistance": sr["resistance"],
        "near_support": sr["near_support"], "near_resistance": sr["near_resistance"],
        "trend_score": ts, "mean_rev_score": ms, "breakout_score": bks, "momentum_pred_score": mps,
        "ensemble_score": es, "confidence": conf, "entry_score": entry_score, "vwap": vwap,
        "full_percentile": round(full_percentile, 1),
        "backtest": bt, "weekly": wk, "position": ps,
        "volume_24h": vol_24h,
    }


# ============================================
# 메시지 포맷
# ============================================
def get_score_grade(s):
    if s >= 80:   return "🅰️"
    elif s >= 60: return "🅱️"
    elif s >= 40: return "🅲"
    elif s >= 20: return "🅳"
    else:         return "🅴"


def _fmt_krw(v):
    if v >= 1_000_000:   return f"₩{v/1_000_000:.2f}M"
    elif v >= 1_000:     return f"₩{v/1_000:.1f}K"
    else:                return f"₩{v:,.0f}"


def format_signal_message(r):
    s = r["signal"]
    if s == "STRONG_BUY":   h = "🟢🟢🟢 <b>강력 매수</b>"
    elif s == "BUY":        h = "🟢 <b>매수 신호</b>"
    elif s == "STRONG_CLOSE": h = "🔴🔴🔴 <b>강력 청산</b>"
    elif s == "CLOSE":      h = "🔴 <b>청산 신호</b>"
    else: return None

    ps, bt = r["position"], r["backtest"]
    ticker_name = r["ticker"].replace("KRW-", "")
    msg = f"""{h} — <b>{ticker_name}</b>
💰 {_fmt_krw(r['price'])} ({r['daily_change']:+.1f}%)
🎯 신뢰도: {r['confidence']:.0f}/100 {get_score_grade(r['confidence'])}"""

    if "BUY" in s:
        msg += f"""
💵 추천 투자: {_fmt_krw(ps['position_krw'])} ({ps['position_pct']:.0f}%) [{ps['method']}]
🛡️ 손절: {_fmt_krw(r['stop_loss'])} | 익절: {_fmt_krw(r['take_profit'])}"""

    msg += f"""
📊 지지 {_fmt_krw(r['support'])} | 저항 {_fmt_krw(r['resistance'])}
📈 백테스트({bt['total_trades']}회): 승률 {bt['win_rate']*100:.0f}% 평균{bt['avg_pnl']:+.1f}%
📐 Sharpe {bt['sharpe']:.1f} | MDD {bt['max_dd']:.0f}% | Calmar {bt['calmar']:.1f}
🔮 모멘텀예측: {r.get('momentum_pred_score', 0):+.0f}"""

    al = []
    if r["volume_spike"]: al.append(f"거래량 {r['volume_ratio']:.1f}x")
    if r["is_surge"]:     al.append("급등" if r["daily_change"] > 0 else "급락")
    if al: msg += "\n⚠️ " + " | ".join(al)

    return msg


def format_status_message(results, regime_info, fear_greed):
    now = utc_now().strftime('%Y-%m-%d %H:%M')
    msg = f"🪙 <b>코인 리포트 v5.48</b> ({now} UTC)\n"
    msg += f"🧠 공포탐욕: {format_fear_greed(fear_greed)}\n"
    msg += f"🌍 시장(BTC): {get_regime_emoji(regime_info['regime'])}\n"

    for r in results:
        if r["signal"] == "NO_DATA":
            msg += f"\n⚠️ {r['ticker']}: 데이터 없음"
            continue
        tr   = "📈" if r["sma_short"] > r["sma_long"] else "📉"
        es   = r["ensemble_score"]
        name = r["ticker"].replace("KRW-", "")
        if es > 0:   d = f"매수 {r['confidence']:.0f}점"
        elif es < 0: d = f"청산 {r['confidence']:.0f}점"
        else:        d = "중립"

        msg += f"\n{tr} <b>{name}</b> {_fmt_krw(r['price'])} ({r['daily_change']:+.1f}%)"
        msg += f"\n   {r['signal']} ({d})"

        fl = []
        if r["volume_spike"]:    fl.append("거래량↑")
        if r["is_surge"]:        fl.append("급변동")
        if r["near_support"]:    fl.append("지지근접")
        if r["near_resistance"]: fl.append("저항근접")
        if fl: msg += f" 🚩 {', '.join(fl)}"

    return msg


# ============================================
# 차트 생성
# ============================================
def generate_chart(ticker, data, result):
    try:
        df = data.tail(60).copy()
        if len(df) < 20:
            return None

        mc = mpf.make_marketcolors(
            up="#26a69a", down="#ef5350", edge="inherit", wick="inherit",
            volume={"up": "#26a69a80", "down": "#ef535080"},
        )
        style = mpf.make_mpf_style(
            marketcolors=mc, facecolor="#1e1e2e", edgecolor="#1e1e2e",
            figcolor="#1e1e2e", gridcolor="#333344", gridstyle="--", y_on_right=True,
            rc={"axes.labelcolor": "#ccc", "xtick.color": "#999", "ytick.color": "#999"},
        )

        close = df["Close"]
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(min(50, len(close))).mean()
        bb_u, _, bb_l = calc_bollinger(close, period=min(20, len(close)))
        rsi   = calc_rsi(close, period=min(14, len(close) - 1))

        ap = [
            mpf.make_addplot(sma20, color="#ffd700", width=1.0),
            mpf.make_addplot(sma50, color="#00bcd4", width=1.0),
            mpf.make_addplot(bb_u,  color="#666666", width=0.7, linestyle="--"),
            mpf.make_addplot(bb_l,  color="#666666", width=0.7, linestyle="--"),
            mpf.make_addplot(rsi, panel=2, color="#ba68c8", width=1.2, ylabel="RSI"),
            mpf.make_addplot(pd.Series(70, index=df.index), panel=2, color="#ef535060", width=0.5, linestyle="--"),
            mpf.make_addplot(pd.Series(30, index=df.index), panel=2, color="#26a69a60", width=0.5, linestyle="--"),
        ]

        sig = result["signal"]
        if "BUY" in sig:
            m = pd.Series(float("nan"), index=df.index)
            m.iloc[-1] = float(df["Low"].iloc[-1]) * 0.98
            ap.append(mpf.make_addplot(m, type="scatter", marker="^", markersize=120, color="#26a69a"))
        elif "CLOSE" in sig:
            m = pd.Series(float("nan"), index=df.index)
            m.iloc[-1] = float(df["High"].iloc[-1]) * 1.02
            ap.append(mpf.make_addplot(m, type="scatter", marker="v", markersize=120, color="#ef5350"))

        fig, axes = mpf.plot(
            df, type="candle", style=style, addplot=ap, volume=True,
            panel_ratios=(3, 1, 1), figsize=(10, 7), returnfig=True, tight_layout=True,
        )

        name  = ticker.replace("KRW-", "")
        label = {"STRONG_BUY": "STRONG BUY", "BUY": "BUY",
                 "STRONG_CLOSE": "STRONG SELL", "CLOSE": "SELL"}.get(sig, sig)
        axes[0].set_title(
            f"{name}  {_fmt_krw(result['price'])}  ({result['daily_change']:+.1f}%)  |  "
            f"{label}  conf:{result['confidence']:.0f}",
            color="#ffffff", fontsize=13, fontweight="bold", loc="left", pad=10,
        )
        if "BUY" in sig:
            axes[0].axhline(y=result["stop_loss"],   color="#ef5350", lw=0.8, ls=":", alpha=0.7)
            axes[0].axhline(y=result["take_profit"], color="#26a69a", lw=0.8, ls=":", alpha=0.7)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                    facecolor="#1e1e2e", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"   ⚠️ {ticker} 차트 생성 실패: {e}")
        return None


def get_risk_level(trade_history, daily_dd_pct):
    """단계별 리스크 레벨 판정. daily_dd_pct는 양수 값 (예: 3.0 = -3%)"""
    # 최근 6시간 내 SL 연속 카운트
    now = utc_now()
    recent_sls = 0
    for t in reversed(trade_history):
        if t.get("side") not in ("SELL", "PARTIAL_SELL"):
            continue
        reason = t.get("reason", "")
        if reason not in ("STOP_LOSS", "CATASTROPHIC_STOP"):
            continue
        try:
            ts = datetime.fromisoformat(t["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            hours_ago = (now - ts).total_seconds() / 3600
            if hours_ago <= RISK_SL_LOOKBACK_HOURS:
                recent_sls += 1
            else:
                break
        except (ValueError, TypeError, KeyError):
            continue

    # Level 2: 경고
    if daily_dd_pct >= RISK_LEVEL_2_DD or recent_sls >= 3:
        return 2, recent_sls, "경고"
    # Level 1: 주의
    if daily_dd_pct >= RISK_LEVEL_1_DD or recent_sls >= 2:
        return 1, recent_sls, "주의"
    # Level 0: 정상
    return 0, recent_sls, "정상"


# ============================================
# 메인
# ============================================
def main():
    _ver_m = __import__('re').search(r'v(\d+\.\d+)', __doc__ or '')
    _banner_ver = _ver_m.group(0) if _ver_m else 'v5.9'
    now = utc_now()
    print(f"{'='*60}\n🪙 Coin Alert {_banner_ver} — Upbit KRW 자동매매 (평균회귀)")
    print(f"   {now.strftime('%Y-%m-%d %H:%M:%S')} UTC | 자본: ₩{INITIAL_CAPITAL:,}")
    print(f"   비용: 수수료 {COMMISSION_BPS}bps + 슬리피지 {SLIPPAGE_BPS}bps = 편도 {TOTAL_COST_BPS}bps")
    print(f"   최대 노출: {MAX_PORTFOLIO_EXPOSURE*100:.0f}% | 종목당 상한: {MAX_POSITION_PCT*100:.0f}%")
    sl_mode = f"분할SL(-{PARTIAL_SL_1ST_PCT}%→{PARTIAL_SL_RATIO*100:.0f}%, -{PARTIAL_SL_2ND_PCT}%→나머지)" if PARTIAL_SL_ENABLED else f"SL DCA전-{LOSS_CUT_PCT}%/DCA후-{LOSS_CUT_PCT_DCA}%"
    print(f"   분할매수: 첫진입 {INITIAL_BUY_RATIO*100:.0f}% → DCA -{DCA_DROP_PCT}% 시 나머지 | {sl_mode}")
    print(f"   분할익절: TP1 +{PROFIT_TARGET_1ST}%({PARTIAL_SELL_RATIO_1*100:.0f}%) → TP2 +{PROFIT_TARGET_2ND}%({PARTIAL_SELL_RATIO_2*100:.0f}%) → TP3 +{PROFIT_TARGET_3RD}%(전량) | RSI상한: {RSI_BUY_CEILING}")
    print(f"   트레일링: +{TRAILING_ACTIVATE_PCT}% 활성 → -{TRAILING_CALLBACK_PCT}% 콜백 | 거래대금≥{MIN_VOLUME_24H/1e8:.0f}억")
    print(f"   신호매도 가드: {MIN_SIGNAL_EXIT_HOURS}h + |PnL|≥{MIN_SIGNAL_EXIT_PNL}% | 최대: {MAX_CONCURRENT_POSITIONS}개 | 서킷: MDD {CIRCUIT_BREAKER_DD*100:.0f}%")
    print(f"   분석 {len(TICKERS)}종목: {', '.join(t.replace('KRW-', '') for t in TICKERS)}")
    print(f"   자동매매: {'✅ 활성' if AUTO_TRADE_ENABLED else '❌ 비활성 (알림만)'}")
    # v5.49: ML 모델 상태
    try:
        from trade_model import predict, MODEL_FILE
        import os as _os
        if _os.path.exists(MODEL_FILE):
            print(f"   🧠 매매 예측 모델: 활성 (trade_model.pkl)")
        else:
            print(f"   🧠 매매 예측 모델: 대기 (데이터 축적 중)")
    except ImportError:
        pass
    print(f"{'='*60}\n")

    # Phase 1: 데이터 & 분석
    fg = get_crypto_fear_greed()
    if fg:
        print(f"🧠 코인 공포탐욕: {fg['score']} ({fg['rating']})")

    print("📥 전 종목 데이터 조회 중...")
    signal_data, bt_data = fetch_all_data()

    # BTC 기반 레짐 감지
    btc_signal = signal_data.get("KRW-BTC")
    btc_bt     = bt_data.get("KRW-BTC")
    if btc_signal is not None and len(btc_signal) >= 200:
        regime_info = detect_market_regime(btc_signal)
    elif btc_bt is not None and len(btc_bt) >= 200:
        regime_info = detect_market_regime(btc_bt)
    else:
        regime_info = {"regime": "SIDEWAYS", "adx": 15, "vol_20": 50,
                       "above_sma50": True, "above_sma200": True}
    regime_weights = get_regime_strategy_weights(regime_info["regime"])
    threshold      = get_regime_threshold(regime_info["regime"])
    _rs = get_regime_scoring(regime_info["regime"])
    print(f"🌍 시장 레짐(BTC): {get_regime_emoji(regime_info['regime'])} "
          f"| ADX:{regime_info['adx']:.1f} | 변동성:{regime_info['vol_20']:.1f}% "
          f"| 임계값:{threshold}")
    print(f"   레짐 스코어링({regime_info['regime']}): RSI매수≤{_rs['rsi_3pt']}/{_rs['rsi_1pt']} | 진입≥{_rs['min_entry']}점 | TP1 {_rs['tp1_pct']}% | RSI매도≥{_rs['sell_trigger']}")

    # 포트폴리오 동기화
    portfolio = sync_portfolio_with_upbit(load_portfolio()) if AUTO_TRADE_ENABLED else load_portfolio()
    capital   = fetch_actual_capital()  # 가용 현금 (KRW)
    order_log = load_order_log()

    # 레짐을 _meta에 저장 (대시보드에서 표시용)
    if AUTO_TRADE_ENABLED:
        meta = portfolio.get("_meta", {})
        meta["regime"] = regime_info["regime"]
        portfolio["_meta"] = meta

    # v4.0: _sell_memory 만료 정리 (14일 초과 항목 제거)
    sell_memory = portfolio.get("_sell_memory", {})
    expired = [t for t, v in sell_memory.items()
               if (utc_now() - datetime.fromisoformat(v.get("date", utc_now().isoformat()))).days > 14]
    for t in expired:
        del sell_memory[t]
        print(f"   🗑️ {t.replace('KRW-', '')} 매도가 기억 만료 (14일 초과)")
    if expired:
        portfolio["_sell_memory"] = sell_memory

    # v2.3: 총 자산 = 가용 현금 + 보유 코인 가치 (노출/포지션 사이징 기준)
    portfolio_value = 0
    for _t, _pos in portfolio.items():
        if _t in ("_meta", "_sell_memory"):
            continue
        _vol = _pos.get("volume", 0)
        if _t in signal_data and len(signal_data[_t]) > 0:
            _price = float(signal_data[_t]["Close"].iloc[-1])
        else:
            _price = _pos.get("entry_price", 0)
        portfolio_value += _vol * _price
    total_capital = capital + portfolio_value
    if portfolio_value > 0:
        print(f"   📊 보유 가치: {_fmt_krw(portfolio_value)} | 총 자산: {_fmt_krw(total_capital)}")

    # 전 종목 분석
    print("\n📊 분석 시작...")
    results = []
    for ticker in TICKERS:
        sig_df = signal_data.get(ticker)
        bt_df  = bt_data.get(ticker)
        if sig_df is None:
            results.append({"ticker": ticker, "signal": "NO_DATA"})
            print(f"   ⚠️ {ticker}: 데이터 없음")
            continue
        r = analyze_ticker(
            ticker, sig_df, regime_info, regime_weights, fg,
            btc_data=btc_signal, backtest_data=bt_df, capital=total_capital,
        )
        results.append(r)
        name = ticker.replace("KRW-", "")
        _es = r.get('ensemble_score', 0)
        _conf = r.get('confidence', 0)
        _rsi = r.get('rsi', 0)
        _adx = r.get('adx', 0)
        print(f"   {name}: {r['signal']} (앙상블:{_es:+.1f} 신뢰:{_conf}/100 "
              f"RSI:{_rsi:.0f} ADX:{_adx:.0f} 진입:{r.get('entry_score', 0)}점 모멘텀:{r.get('momentum_pred_score', 0):+.0f})")
        _bt = r.get('backtest', {})
        print(f"      손절:{_fmt_krw(r.get('stop_loss', 0))} 익절:{_fmt_krw(r.get('take_profit', 0))} "
              f"Sharpe:{_bt.get('sharpe', 0):.1f}")

    # v5.2: 고아 포지션 매도 체크 — TICKERS에서 제거됐지만 아직 보유 중인 종목
    orphan_tickers = [t for t in portfolio if t not in ("_meta", "_sell_memory") and t not in TICKERS]
    if orphan_tickers:
        print(f"\n🔍 고아 포지션 감지: {', '.join(t.replace('KRW-', '') for t in orphan_tickers)}")
        for ticker in orphan_tickers:
            name = ticker.replace("KRW-", "")
            try:
                cur_price = pyupbit.get_current_price(ticker)
                if cur_price and cur_price > 0:
                    results.append({
                        "ticker": ticker, "signal": "CLOSE", "price": cur_price,
                        "close_reason": "ORPHAN_POSITION",
                        "ensemble_score": 0, "confidence": 0, "rsi": 0, "adx": 0,
                        "position": {"position_krw": 0, "position_pct": 0},
                        "stop_loss": 0, "take_profit": 0,
                        "backtest": {"sharpe": 0},
                    })
                    pos = portfolio[ticker]
                    pnl_pct = (cur_price / pos["entry_price"] - 1) * 100 if pos["entry_price"] > 0 else 0
                    print(f"   🚨 {name} 고아 포지션 → 매도 예정 (현재가 {_fmt_krw(cur_price)}, PnL {pnl_pct:+.1f}%)")
                else:
                    print(f"   ⚠️ {name} 현재가 조회 실패 — 다음 사이클에서 재시도")
            except Exception as e:
                print(f"   ⚠️ {name} 고아 포지션 가격 조회 오류: {e}")

    # Phase 2: 서킷브레이커
    # v2.1: 알림 모드에서는 CB 계산이 부정확하므로 (capital=INITIAL_CAPITAL 고정) 매매 차단만 적용
    cb_triggered, drawdown, ref_val, cb_type = check_circuit_breaker(
        portfolio, capital, results, mutate_meta=AUTO_TRADE_ENABLED)
    can_trade = AUTO_TRADE_ENABLED and not cb_triggered

    # v5.48: 단계별 리스크 레벨 체크
    risk_level = 0
    risk_sl_count = 0
    risk_label = "정상"
    position_size_mult = 1.0
    if AUTO_TRADE_ENABLED:
        trade_hist = _load_trade_history()
        daily_dd_pct = drawdown * 100 if cb_type == "DAILY" else 0
        # daily_dd가 OK여도 meta에서 직접 계산
        meta = portfolio.get("_meta", {})
        if meta.get("daily_dd"):
            daily_dd_pct = max(daily_dd_pct, meta["daily_dd"] * 100)
        risk_level, risk_sl_count, risk_label = get_risk_level(trade_hist, daily_dd_pct)
        if risk_level >= 2:
            position_size_mult = RISK_LEVEL_2_SIZE
            print(f"   🚨 리스크 Level 2 ({risk_label}): 신규 매수 차단 (DD -{daily_dd_pct:.1f}%, SL {risk_sl_count}건/6h)")
            send_telegram(f"🚨 <b>리스크 Level 2</b> ({risk_label})\n일일 DD -{daily_dd_pct:.1f}% | SL {risk_sl_count}건/6h\n신규 매수 차단 중")
        elif risk_level >= 1:
            position_size_mult = RISK_LEVEL_1_SIZE
            print(f"   ⚠️ 리스크 Level 1 ({risk_label}): 포지션 사이징 {RISK_LEVEL_1_SIZE*100:.0f}% (DD -{daily_dd_pct:.1f}%, SL {risk_sl_count}건/6h)")

    if cb_triggered and AUTO_TRADE_ENABLED:
        cur_val = portfolio.get('_meta', {}).get('last_value', 0)
        if cb_type == "DAILY":
            msg = (f"🚨 서킷브레이커 발동! (일일 낙폭)\n"
                   f"금일 낙폭 {drawdown*100:.1f}% ≥ {DAILY_DD_LIMIT*100:.0f}%\n"
                   f"금일 시작 ₩{ref_val:,.0f} → 현재 ₩{cur_val:,.0f}\n"
                   f"자동매매 일시 중단")
        else:
            msg = (f"🚨 서킷브레이커 발동! (MDD)\n"
                   f"포트폴리오 MDD {drawdown*100:.1f}% ≥ {CIRCUIT_BREAKER_DD*100:.0f}%\n"
                   f"고점 ₩{ref_val:,.0f} → 현재 ₩{cur_val:,.0f}\n"
                   f"자동매매 일시 중단")
        print(f"\n🚨 {msg}")
        send_telegram(msg)
    elif cb_triggered and not AUTO_TRADE_ENABLED:
        print(f"\n⚠️ 서킷브레이커 감지 ({cb_type}) — 알림 모드에서는 추정치 (실제 자산과 차이 가능)")

    # Phase 3: 매매 실행
    print("\n💹 매매 판단...")
    # webhook 공통 데이터: 레짐 + BTC 24h 변화율
    _wh_regime = regime_info.get("regime", "")
    _wh_btc_chg = 0.0
    if btc_signal is not None and len(btc_signal) >= 24:
        _btc_now = float(btc_signal["Close"].iloc[-1])
        _btc_24h = float(btc_signal["Close"].iloc[-24])
        _wh_btc_chg = round((_btc_now / _btc_24h - 1) * 100, 2) if _btc_24h > 0 else 0.0
    portfolio_tickers  = {k for k in portfolio if k not in ("_meta", "_sell_memory")}
    total_exposure     = sum(
        portfolio[t].get("volume", 0) * r["price"] / total_capital
        for r in results if r["signal"] != "NO_DATA"
        for t in [r["ticker"]] if t in portfolio
    ) if total_capital > 0 else 0
    pending_buy_tickers = []
    pending_exposure   = 0.0
    signal_fired       = False


    for r in results:
        if r["signal"] == "NO_DATA":
            continue

        ticker = r["ticker"]

        # v5.39: 레짐별 적응형 매도 — 시장 상황에 따라 TP1/RSI 매도 기준 변동
        regime_sell = get_regime_scoring(regime_info["regime"])
        regime_tp1 = regime_sell["tp1_pct"]          # BEAR:2%, SIDEWAYS:3%, BULL:4%
        regime_sell_trigger = regime_sell["sell_trigger"]  # BEAR:60, SIDEWAYS:70, BULL:80

        if ticker in portfolio and ticker != "_meta" and ticker != "_sell_memory":
            pos = portfolio[ticker]
            entry_p = pos["entry_price"]
            pnl_pct = (r["price"] / entry_p - 1) * 100 if entry_p > 0 else 0
            name = ticker.replace("KRW-", "")

            # 보유시간 계산 (공통)
            hold_hours = MIN_HOLD_HOURS  # 기본값
            hold_days = 0
            entry_date_str = pos.get("entry_date")
            if entry_date_str and entry_date_str != "synced":
                try:
                    entry_dt = datetime.fromisoformat(entry_date_str)
                    if entry_dt.tzinfo is None:
                        entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                    hold_hours = (utc_now() - entry_dt).total_seconds() / 3600
                    hold_days = hold_hours / 24
                except (ValueError, TypeError):
                    pass

            # v5.20.1: 3단계 분할 익절 — TP1(3%) 50% → TP2(7%) 30% → TP3(10%) 전량
            tp_level = pos.get("tp_level", 0)  # 0=미익절, 1=TP1완료, 2=TP2완료

            # TP1: 레짐별 목표 (BEAR:2%, SIDEWAYS:3%, BULL:4%)에서 50% 매도
            if pnl_pct >= regime_tp1 and tp_level < 1:
                vol = pos.get("volume", 0)
                sell_vol = vol * PARTIAL_SELL_RATIO_1
                if can_trade and sell_vol > 0:
                    order = execute_sell(ticker, sell_vol)
                    if order:
                        record_order(order_log, ticker, "SELL")
                        record_trade(ticker, "PARTIAL_SELL", r["price"], sell_vol, sell_vol * r["price"], "TP1", entry_p, pnl_pct)
                        pos["tp_level"] = 1
                        pos["partial_taken"] = True  # 하위 호환
                        pos["volume"] = vol - sell_vol
                        signal_fired = True
                        sold_value = sell_vol * r["price"]
                        total_exposure = max(0, total_exposure - sold_value / total_capital)
                        capital += sold_value * (1 - TOTAL_COST_BPS / 10000)
                        send_telegram(
                            f"💰 <b>{name}</b> TP1 익절 ({PARTIAL_SELL_RATIO_1*100:.0f}%)\n"
                            f"진입{_fmt_krw(entry_p)} → 현재{_fmt_krw(r['price'])} ({pnl_pct:+.1f}%)\n"
                            f"매도: {sell_vol:.8g} | 잔여: {pos['volume']:.8g}")
                        print(f"   💰 {name} TP1 익절: {pnl_pct:+.1f}% ≥ {regime_tp1}% (50% 매도, {regime_info['regime']})")
                        _send_trade_analysis_webhook(
                            ticker, "PARTIAL_SELL", r["price"], sell_vol, sell_vol * r["price"],
                            "TP1", entry_p, pnl_pct,
                            extra_data={"hold_hours": hold_hours, "entry_rsi": round(r.get("rsi", 0), 1),
                                        "exit_rsi": round(r.get("rsi", 0), 1), "entry_score": round(r.get("ensemble_score", 0), 1),
                                        "market_regime": _wh_regime, "btc_change_pct": _wh_btc_chg}
                        )
                elif not can_trade:
                    print(f"   💰 {name} TP1 도달 +{pnl_pct:.1f}% (자동매매 비활성)")

            # TP2: +7%에서 잔여의 60% 매도 (전체 기준 30%)
            if pnl_pct >= PROFIT_TARGET_2ND and tp_level == 1:
                vol = pos.get("volume", 0)
                sell_vol = vol * PARTIAL_SELL_RATIO_2
                if can_trade and sell_vol > 0:
                    order = execute_sell(ticker, sell_vol)
                    if order:
                        record_order(order_log, ticker, "SELL")
                        record_trade(ticker, "PARTIAL_SELL", r["price"], sell_vol, sell_vol * r["price"], "TP2", entry_p, pnl_pct)
                        pos["tp_level"] = 2
                        pos["volume"] = vol - sell_vol
                        signal_fired = True
                        sold_value = sell_vol * r["price"]
                        total_exposure = max(0, total_exposure - sold_value / total_capital)
                        capital += sold_value * (1 - TOTAL_COST_BPS / 10000)
                        send_telegram(
                            f"💰 <b>{name}</b> TP2 익절 (잔여의 {PARTIAL_SELL_RATIO_2*100:.0f}%)\n"
                            f"진입{_fmt_krw(entry_p)} → 현재{_fmt_krw(r['price'])} ({pnl_pct:+.1f}%)\n"
                            f"매도: {sell_vol:.8g} | 잔여: {pos['volume']:.8g}")
                        print(f"   💰 {name} TP2 익절: {pnl_pct:+.1f}% (잔여 50% 매도)")
                        _send_trade_analysis_webhook(
                            ticker, "PARTIAL_SELL", r["price"], sell_vol, sell_vol * r["price"],
                            "TP2", entry_p, pnl_pct,
                            extra_data={"hold_hours": hold_hours, "entry_rsi": round(r.get("rsi", 0), 1),
                                        "exit_rsi": round(r.get("rsi", 0), 1), "entry_score": round(r.get("ensemble_score", 0), 1),
                                        "market_regime": _wh_regime, "btc_change_pct": _wh_btc_chg}
                        )
                elif not can_trade:
                    print(f"   💰 {name} TP2 도달 +{pnl_pct:.1f}% (자동매매 비활성)")

            # TP3: +10%에서 전량 매도
            if pnl_pct >= PROFIT_TARGET_3RD:
                r["signal"] = "CLOSE"
                r["close_reason"] = "PROFIT_TARGET"
                print(f"   🎯 {name} TP3 익절: {pnl_pct:+.1f}% ≥ {PROFIT_TARGET_3RD}%")

            # v5.20.1: CATASTROPHIC STOP — 갭다운 즉시 매도 (MIN_HOLD_HOURS 무시)
            elif pnl_pct <= -CATASTROPHIC_STOP_PCT:
                r["signal"] = "CLOSE"
                r["close_reason"] = "CATASTROPHIC_STOP"
                print(f"   🚨 {name} 긴급 손절: {pnl_pct:+.1f}% ≤ -{CATASTROPHIC_STOP_PCT}% (즉시 매도)")

            # v4.0: 시간 스탑 — 보유 기간 MAX_HOLD_DAYS 초과 (SL보다 우선)
            elif hold_days >= MAX_HOLD_DAYS:
                r["signal"] = "CLOSE"
                r["close_reason"] = "TIME_STOP"
                print(f"   ⏰ {name} 시간 스탑: {hold_days:.1f}일 ≥ {MAX_HOLD_DAYS}일")

            # v5.39: TP1_BREAKEVEN_SL — TP1 후 잔여 포지션은 진입가가 손절선
            # v5.31: 고정 손절 — TIME_STOP/TRAILING 이후 최후의 수단 (손절최소화 대원칙)
            elif tp_level >= 1 and TP1_BREAKEVEN_SL and pnl_pct <= 0 and hold_hours >= MIN_HOLD_HOURS:
                r["signal"] = "CLOSE"
                r["close_reason"] = "BREAKEVEN_STOP"
                print(f"   🛡️ {name} 브레이크이븐 손절: TP1 후 {pnl_pct:+.1f}% ≤ 0% (진입가 이탈)")
            # v5.48: 분할 손절 — SL 1단계(-4%)→50% 매도, SL 2단계(-6%)→나머지 전량
            # v5.44: DCA 여부에 따른 SL 분리 — DCA 미발동 -5%, DCA 후 -4% (평균단가 기준)
            elif hold_hours >= MIN_HOLD_HOURS:
                sl_pct = LOSS_CUT_PCT_DCA if pos.get("dca_count", 0) > 0 else LOSS_CUT_PCT
                sl_partial_done = pos.get("sl_partial_done", False)

                if PARTIAL_SL_ENABLED and not sl_partial_done:
                    # ── 분할 손절 1단계: -4% 도달 시 50% 매도 ──
                    sl1_pct = LOSS_CUT_PCT_DCA if pos.get("dca_count", 0) > 0 else PARTIAL_SL_1ST_PCT
                    if pnl_pct <= -sl1_pct:
                        vol = pos.get("volume", 0)
                        sell_vol = vol * PARTIAL_SL_RATIO
                        partial_sl1_done = False
                        if can_trade and sell_vol > 0:
                            order = execute_sell(ticker, sell_vol)
                            if order:
                                record_order(order_log, ticker, "SELL")
                                record_trade(ticker, "PARTIAL_SELL", r["price"], sell_vol, sell_vol * r["price"], "PARTIAL_SL1", entry_p, pnl_pct)
                                # v5.48: 분할손절 분석 webhook
                                _hold_h = 0
                                try:
                                    _ed = pos.get("entry_date", "")
                                    if _ed and _ed != "synced":
                                        _edt = datetime.fromisoformat(_ed)
                                        if _edt.tzinfo is None:
                                            _edt = _edt.replace(tzinfo=timezone.utc)
                                        _hold_h = round((utc_now() - _edt).total_seconds() / 3600, 1)
                                except Exception:
                                    pass
                                _send_trade_analysis_webhook(
                                    ticker, "PARTIAL_SELL", r["price"], sell_vol, sell_vol * r["price"],
                                    "PARTIAL_SL1", entry_p, pnl_pct,
                                    extra_data={
                                        "hold_hours": _hold_h,
                                        "entry_rsi": round(r.get("rsi", 0), 1),
                                        "exit_rsi": round(r.get("rsi", 0), 1),
                                        "entry_score": round(r.get("ensemble_score", 0), 1),
                                        "market_regime": _wh_regime, "btc_change_pct": _wh_btc_chg,
                                    }
                                )
                                pos["sl_partial_done"] = True
                                pos["volume"] = vol - sell_vol
                                signal_fired = True
                                partial_sl1_done = True
                                sold_value = sell_vol * r["price"]
                                total_exposure = max(0, total_exposure - sold_value / total_capital)
                                capital += sold_value * (1 - TOTAL_COST_BPS / 10000)
                                send_telegram(
                                    f"🛡️ <b>{name}</b> 분할손절 1단계 ({PARTIAL_SL_RATIO*100:.0f}%)\n"
                                    f"PnL {pnl_pct:+.1f}% ≤ -{sl1_pct}%\n"
                                    f"매도: {sell_vol:.8g} | 잔여: {pos['volume']:.8g}\n"
                                    f"반등 대기 → SL2 -{PARTIAL_SL_2ND_PCT}%")
                                print(f"   🛡️ {name} 분할손절 1단계: {pnl_pct:+.1f}% ≤ -{sl1_pct}% ({PARTIAL_SL_RATIO*100:.0f}% 매도, 잔여 대기)")
                            else:
                                print(f"   ⚠️ {name} 분할손절 1단계 주문 실패 → 전량 SL 전환")
                        elif not can_trade:
                            print(f"   🛡️ {name} 분할손절 1단계 감지 ({pnl_pct:+.1f}%, 자동매매 비활성)")
                        # v5.48 fix: 분할SL1 실패 시 전량 SL fallback (SL 미발동 방지)
                        if not partial_sl1_done and pnl_pct <= -sl_pct:
                            r["signal"] = "CLOSE"
                            r["close_reason"] = "STOP_LOSS"
                            print(f"   🛡️ {name} 전량손절 (분할SL 실패 fallback): {pnl_pct:+.1f}% ≤ -{sl_pct}%")

                elif PARTIAL_SL_ENABLED and sl_partial_done:
                    # ── 분할 손절 2단계: -6% 도달 시 나머지 전량 매도 ──
                    if pnl_pct <= -PARTIAL_SL_2ND_PCT:
                        r["signal"] = "CLOSE"
                        r["close_reason"] = "STOP_LOSS"
                        print(f"   🛡️ {name} 분할손절 2단계: {pnl_pct:+.1f}% ≤ -{PARTIAL_SL_2ND_PCT}% (잔여 전량 매도)")

                elif pnl_pct <= -sl_pct:
                    # 분할 손절 비활성 시 기존 로직: 전량 매도
                    r["signal"] = "CLOSE"
                    r["close_reason"] = "STOP_LOSS"
                    sl_label = f"DCA평단-{sl_pct}%" if pos.get("dca_count", 0) > 0 else f"-{sl_pct}%"
                    print(f"   🛡️ {name} 손절: {pnl_pct:+.1f}% ≤ -{sl_pct}% ({sl_label})")
            elif pnl_pct <= -LOSS_CUT_PCT:
                print(f"   ⏳ {name} 손절 유예 (보유 {hold_hours:.1f}h < {MIN_HOLD_HOURS}h)")

            # v4.1: 트레일링 익절 — 수익 고점 대비 콜백 시 매도
            if r["signal"] not in ("CLOSE", "STRONG_CLOSE"):
                high_pnl = max(pos.get("high_pnl", 0), pnl_pct)
                pos["high_pnl"] = high_pnl
                if high_pnl >= TRAILING_ACTIVATE_PCT and (high_pnl - pnl_pct) >= TRAILING_CALLBACK_PCT:
                    r["signal"] = "CLOSE"
                    r["close_reason"] = "TRAILING_STOP"
                    print(f"   📈 {name} 트레일링 익절: 고점 {high_pnl:+.1f}% → 현재 {pnl_pct:+.1f}% (콜백 {high_pnl-pnl_pct:.1f}%)")

            # v5.40: 레짐별 RSI 과매수 익절 — 분할매도 대원칙 준수
            # TP1 미달(pnl < regime_tp1) 시 전량매도 금지, TP1 분할매도 기회 보장
            # tp_level==0이면 TP1처럼 50% 분할매도, tp_level>=1이면 전량매도 허용
            if r["signal"] not in ("CLOSE", "STRONG_CLOSE") and pnl_pct >= regime_tp1:
                cur_rsi = r.get("rsi", 50)
                if cur_rsi >= regime_sell_trigger and hold_hours >= MIN_HOLD_HOURS:
                    if tp_level >= 1:
                        # TP1 이미 완료 → 전량매도 OK
                        r["signal"] = "CLOSE"
                        r["close_reason"] = "RSI_SELL"
                        print(f"   📊 {name} RSI 익절: RSI {cur_rsi:.0f} ≥ {regime_sell_trigger} ({regime_info['regime']}) | PnL {pnl_pct:+.1f}% (전량)")
                    else:
                        # tp_level==0: TP1 미완료 → 50% 분할매도 (대원칙: 분할매도 우선)
                        vol = pos.get("volume", 0)
                        sell_vol = vol * PARTIAL_SELL_RATIO_1
                        if can_trade and sell_vol > 0:
                            order = execute_sell(ticker, sell_vol)
                            if order:
                                record_order(order_log, ticker, "SELL")
                                record_trade(ticker, "PARTIAL_SELL", r["price"], sell_vol, sell_vol * r["price"], "RSI_SELL_TP1", entry_p, pnl_pct)
                                pos["tp_level"] = 1
                                pos["partial_taken"] = True
                                pos["volume"] = vol - sell_vol
                                signal_fired = True
                                sold_value = sell_vol * r["price"]
                                total_exposure = max(0, total_exposure - sold_value / total_capital)
                                capital += sold_value * (1 - TOTAL_COST_BPS / 10000)
                                send_telegram(
                                    f"📊 <b>{name}</b> RSI 분할익절 ({PARTIAL_SELL_RATIO_1*100:.0f}%)\n"
                                    f"RSI {cur_rsi:.0f} ≥ {regime_sell_trigger} ({regime_info['regime']})\n"
                                    f"진입{_fmt_krw(entry_p)} → 현재{_fmt_krw(r['price'])} ({pnl_pct:+.1f}%)\n"
                                    f"매도: {sell_vol:.8g} | 잔여: {pos['volume']:.8g}")
                                print(f"   📊 {name} RSI 분할익절: RSI {cur_rsi:.0f} ≥ {regime_sell_trigger} ({regime_info['regime']}) | PnL {pnl_pct:+.1f}% (50% 매도)")
                                _send_trade_analysis_webhook(
                                    ticker, "PARTIAL_SELL", r["price"], sell_vol, sell_vol * r["price"],
                                    "RSI_SELL_TP1", entry_p, pnl_pct,
                                    extra_data={"hold_hours": hold_hours, "entry_rsi": round(r.get("rsi", 0), 1),
                                                "exit_rsi": round(cur_rsi, 1), "entry_score": round(r.get("ensemble_score", 0), 1),
                                                "market_regime": _wh_regime, "btc_change_pct": _wh_btc_chg}
                                )
                        elif not can_trade:
                            print(f"   📊 {name} RSI 과매수 감지 (PnL {pnl_pct:+.1f}%, 자동매매 비활성)")

        # CLOSE 신호: 미보유 시 HOLD
        if r["signal"] in ["CLOSE", "STRONG_CLOSE"] and ticker not in portfolio:
            r["signal"] = "HOLD"

        # v5.20: 신호 매도 Churn 방지 — 최소 보유시간 + 최소 PnL 기준
        if r["signal"] in ["CLOSE", "STRONG_CLOSE"] and ticker in portfolio:
            if r.get("close_reason") not in ("PROFIT_TARGET", "STOP_LOSS", "CATASTROPHIC_STOP", "TIME_STOP", "TRAILING_STOP", "BREAKEVEN_STOP", "RSI_SELL", "ORPHAN_POSITION"):
                entry_date_str = portfolio[ticker].get("entry_date")
                entry_p = portfolio[ticker].get("entry_price", 0)
                sig_pnl = (r["price"] / entry_p - 1) * 100 if entry_p > 0 else 0
                if entry_date_str and entry_date_str != "synced":
                    try:
                        entry_dt = datetime.fromisoformat(entry_date_str)
                        if entry_dt.tzinfo is None:
                            entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                        hold_hours = (utc_now() - entry_dt).total_seconds() / 3600
                        name = ticker.replace("KRW-", "")
                        # v5.20: 신호매도는 MIN_SIGNAL_EXIT_HOURS 적용 (기존 MIN_HOLD_HOURS 대체)
                        if hold_hours < MIN_SIGNAL_EXIT_HOURS:
                            r["signal"] = "HOLD"
                            print(f"   ⏳ {name} 신호 매도 유예 (보유 {hold_hours:.1f}h < {MIN_SIGNAL_EXIT_HOURS}h)")
                        # v5.20.1: 손실 구간 신호매도 완전 차단 (손절은 SL이 전담)
                        elif sig_pnl < 0:
                            r["signal"] = "HOLD"
                            print(f"   ⏳ {name} 신호 매도 유예 (손실 {sig_pnl:+.1f}% — SL(-{LOSS_CUT_PCT}%)까지 대기)")
                        # v5.20: 이익 구간에서도 +1% 미만이면 매도 차단 (수수료 Churn 방지)
                        elif sig_pnl < MIN_SIGNAL_EXIT_PNL:
                            r["signal"] = "HOLD"
                            print(f"   ⏳ {name} 신호 매도 유예 (PnL {sig_pnl:+.1f}% < +{MIN_SIGNAL_EXIT_PNL}%)")
                    except (ValueError, TypeError):
                        pass

    # Step 2: 신호 강도 기준 정렬 (v2.3)
    # 청산 우선 → 매수는 앙상블 점수 내림차순 → HOLD
    # 높은 점수 종목이 노출 한도를 우선 확보
    results_sorted = sorted(results, key=lambda x: (
        0 if x.get("signal") in ("CLOSE", "STRONG_CLOSE") else
        1 if x.get("signal") in ("BUY", "STRONG_BUY") else 2,
        -abs(x.get("ensemble_score", 0))
    ))
    buy_order = [r for r in results_sorted if r.get("signal") in ("BUY", "STRONG_BUY")]
    if buy_order:
        order_str = ", ".join(
            f"{r['ticker'].replace('KRW-', '')}({r['ensemble_score']:+.0f})"
            for r in buy_order
        )
        print(f"   📊 매수 우선순위: {order_str}")

    # Step 3: 매매 실행 (정렬된 순서)
    for r in results_sorted:
        if r["signal"] in ("NO_DATA", "HOLD"):
            continue

        ticker = r["ticker"]
        ps = r["position"]

        # === 매수 ===
        if r["signal"] in ["BUY", "STRONG_BUY"]:
            name = ticker.replace("KRW-", "")

            # v5.9: BTC 레짐 필터 구현 (20MA 기반 risk-off 차단)
            if BTC_REGIME_FILTER and btc_signal is not None and len(btc_signal) > BTC_REGIME_MA_PERIOD:
                _btc_c = float(btc_signal["Close"].iloc[-1])
                _btc_ma = float(btc_signal["Close"].rolling(BTC_REGIME_MA_PERIOD).mean().iloc[-1])
                if _btc_c <= _btc_ma and ticker not in portfolio:
                    print(f"   \ud83d\udd34 {name} BTC 레짐: BTC={_btc_c/1e6:.1f}M <= {BTC_REGIME_MA_PERIOD}MA={_btc_ma/1e6:.1f}M")
                    continue

            # v4.0: 포지션 수 제한 (동시 보유 MAX_CONCURRENT_POSITIONS)
            current_positions = len([k for k in portfolio if k not in ("_meta", "_sell_memory")])
            if current_positions >= MAX_CONCURRENT_POSITIONS and ticker not in portfolio:
                print(f"   🚫 {name} 포지션 한도: {current_positions}/{MAX_CONCURRENT_POSITIONS}종목 보유 중")
                continue

            # v4.1: 거래대금 필터 — 유동성 부족 종목 차단
            vol_24h = r.get("volume_24h", float("inf"))
            if vol_24h < MIN_VOLUME_24H and ticker not in portfolio:
                print(f"   🚫 {name} 거래대금 부족: {vol_24h/1e8:.0f}억 < {MIN_VOLUME_24H/1e8:.0f}억")
                continue

            # v4.0: 매도가 기억 — 충분히 하락해야 재매수
            sell_memory = portfolio.get("_sell_memory", {})
            if ticker in sell_memory and ticker not in portfolio:
                last_sell_price = sell_memory[ticker]["price"]
                drop_threshold = last_sell_price * (1 - REBUY_DROP_PCT / 100)
                if r["price"] > drop_threshold:
                    drop_pct = (r["price"] / last_sell_price - 1) * 100
                    print(f"   🔒 {name} 재매수 차단: 매도가{_fmt_krw(last_sell_price)} 대비 {drop_pct:+.1f}% (≥-{REBUY_DROP_PCT}% 필요)")
                    continue
                else:
                    del sell_memory[ticker]
                    portfolio["_sell_memory"] = sell_memory
                    print(f"   ✅ {name} 재매수 허용: 매도가 대비 {((r['price']/last_sell_price - 1)*100):+.1f}%")

            # 손절 쿨다운 — 최근 스탑 발동 후 STOP_COOLDOWN_HOURS 이내 재진입 차단
            stop_cd_key = f"{ticker}_STOP_CD"
            stop_cd_time = order_log.get(stop_cd_key)
            if stop_cd_time and ticker not in portfolio:
                try:
                    cd_dt = datetime.fromisoformat(stop_cd_time)
                    cd_elapsed = (utc_now() - cd_dt).total_seconds() / 3600
                    if cd_elapsed < STOP_COOLDOWN_HOURS:
                        print(f"   ⏳ {name} 스탑 쿨다운 ({cd_elapsed:.1f}h < {STOP_COOLDOWN_HOURS}h)")
                        continue
                except (ValueError, TypeError):
                    pass

            if ticker in portfolio:
                pos = portfolio[ticker]
                # v4.0: 분할매수 (DCA) — 진입가 대비 더 떨어지면 추가 매수 (물타기)
                dca_ok = (
                    DCA_ENABLED
                    and pos.get("dca_count", 0) < DCA_MAX_ADDS
                    and r["price"] <= pos["entry_price"] * (1 - DCA_DROP_PCT / 100)
                )
                if dca_ok:
                    # v5.17: full_position_krw 기반 잔여분 계산 (없으면 레거시 fallback)
                    full_krw = pos.get("full_position_krw")
                    if full_krw:
                        current_value = pos.get("volume", 0) * r["price"]
                        add_krw = max(0, full_krw - current_value)
                    else:
                        add_krw = r["position"]["position_krw"] * DCA_ADD_RATIO
                    # v4.1: DCA 시 비중 상한 강제 (MAX_POSITION_PCT 초과 방지)
                    current_pos_value = pos.get("volume", 0) * r["price"]
                    max_pos_value = total_capital * MAX_POSITION_PCT
                    if current_pos_value + add_krw > max_pos_value:
                        add_krw = max(0, max_pos_value - current_pos_value)
                        if add_krw < 5000:
                            print(f"   ⚠️ {name} DCA 차단: 비중 상한 {MAX_POSITION_PCT*100:.0f}% 도달")
                    if can_trade and add_krw >= 5000:
                        order = execute_buy(ticker, add_krw)
                        if order:
                            record_order(order_log, ticker, "BUY")
                            record_trade(ticker, "BUY", r["price"], add_krw / r["price"], add_krw, "DCA",
                                        entry_context=capture_entry_context(ticker, r, regime_info, btc_signal))
                            old_vol = pos.get("volume", 0)
                            add_vol = add_krw / r["price"]
                            new_vol = old_vol + add_vol
                            pos["entry_price"] = (pos["entry_price"] * old_vol + r["price"] * add_vol) / new_vol
                            pos["volume"] = new_vol
                            pos["dca_count"] = pos.get("dca_count", 0) + 1
                            signal_fired = True
                            drop_pct = (r["price"] / pos["entry_price"] - 1) * 100
                            send_telegram(
                                f"📉 <b>{name}</b> 분할매수 {pos['dca_count']}차 (DCA)\n"
                                f"추가 {_fmt_krw(add_krw)} @ {_fmt_krw(r['price'])} ({drop_pct:+.1f}%)\n"
                                f"평균단가: {_fmt_krw(pos['entry_price'])}")
                            print(f"   📉 {name} 분할매수: +{_fmt_krw(add_krw)} @ {_fmt_krw(r['price'])} (평단 {_fmt_krw(pos['entry_price'])})")
                    elif not can_trade:
                        print(f"   📉 {name} 분할매수 조건 충족 (자동매매 비활성)")
                else:
                    print(f"   ℹ️ {name} 이미 보유 중 — 추가 매수 생략")
            else:
                corr_penalty    = calc_correlation_penalty(
                    list(portfolio_tickers) + pending_buy_tickers + [ticker],
                    {t: signal_data[t] for t in signal_data},
                )
                proposed_pct    = ps["position_pct"] / 100
                name            = ticker.replace("KRW-", "")

                # v2.3: 노출 한도 내로 포지션 자동 축소
                remaining = max(0, MAX_PORTFOLIO_EXPOSURE - total_exposure - pending_exposure)
                max_addable = remaining / corr_penalty if corr_penalty > 0 else remaining
                if proposed_pct > max_addable and max_addable >= MIN_POSITION_PCT:
                    old_pct = proposed_pct
                    proposed_pct = max_addable
                    ps = {**ps, "position_pct": proposed_pct * 100,
                          "position_krw": total_capital * proposed_pct}
                    print(f"   📐 {name} 포지션 축소: {old_pct*100:.0f}% → {proposed_pct*100:.0f}% (노출 한도 맞춤)")

                effective_exp   = total_exposure + (pending_exposure + proposed_pct) * corr_penalty

                if effective_exp > MAX_PORTFOLIO_EXPOSURE:
                    print(f"   ⚠️ {name} 노출 여유 부족 ({remaining*100:.1f}% 잔여) — 매수 불가")
                elif ps.get("method") == "BT_REJECT":
                    print(f"   ⚠️ {name} 백테스트 부적합 (Sharpe:{r['backtest'].get('sharpe', 0)}) — 매수 보류")
                elif ps.get("method") == "SKIP":
                    print(f"   ⚠️ {name} 신뢰도 부족 (conf:{r['confidence']:.0f}<30) — 매수 보류")
                elif ps["position_krw"] < 5000:
                    print(f"   ⚠️ {name} 투자금 부족 (₩{ps['position_krw']:,.0f} < 최소 ₩5,000)")
                else:
                    if can_trade:
                        if has_recent_order(order_log, ticker, "BUY"):
                            print(f"   ℹ️ {name} 최근 {ORDER_COOLDOWN_MINUTES}분 내 매수 주문 — 중복 방지")
                        else:
                            # v5.17: 분할매수 — 첫 진입 시 INITIAL_BUY_RATIO만 매수
                            full_krw = ps["position_krw"]
                            buy_krw = full_krw * INITIAL_BUY_RATIO
                            # v5.48: 리스크 레벨에 따른 사이징 조정
                            buy_krw = buy_krw * position_size_mult
                            if buy_krw < 5000:
                                print(f"   🚨 {name} 매수 차단 (리스크 Level {risk_level}: {risk_label})")
                                continue
                            # v5.49: ML 모델 예측 (로깅만, 차단 안 함)
                            try:
                                import math as _math
                                from trade_model import predict as _ml_predict
                                _hour = utc_now().hour
                                _prob = _ml_predict({
                                    "entry_rsi": r.get("rsi", 50),
                                    "exit_rsi": r.get("rsi", 50),
                                    "entry_score": r.get("ensemble_score", 0),
                                    "hold_hours": 0,
                                    "abs_pnl_pct": 0,
                                    "btc_change_pct": 0,
                                    "hour_sin": _math.sin(2 * _math.pi * _hour / 24),
                                    "hour_cos": _math.cos(2 * _math.pi * _hour / 24),
                                })
                                if _prob is not None:
                                    print(f"   🧠 {name} ML 예측점수: {_prob:+.2f} ({'양호' if _prob > 0 else '주의'})")
                            except Exception:
                                pass
                            order = execute_buy(ticker, buy_krw)
                            if order:
                                record_order(order_log, ticker, "BUY")
                                record_trade(ticker, "BUY", r["price"], buy_krw / r["price"], buy_krw, "INITIAL",
                                            entry_context=capture_entry_context(ticker, r, regime_info, btc_signal))
                                pending_exposure += proposed_pct
                                pending_buy_tickers.append(ticker)
                                signal_fired = True
                                # v3.3 fix: 매수 즉시 portfolio에 추가 (entry_date 보존)
                                est_vol = buy_krw / r["price"]
                                portfolio[ticker] = {
                                    "volume": est_vol,
                                    "entry_price": r["price"],
                                    "entry_date": utc_now().isoformat(),
                                    "dca_count": 0,
                                    "full_position_krw": full_krw,  # v5.17: DCA 잔여분 계산용
                                }
                                portfolio_tickers.add(ticker)
                                split_pct = INITIAL_BUY_RATIO * 100
                                send_telegram(
                                    f"📥 <b>{name}</b> 분할매수 1차 ({split_pct:.0f}%)\n"
                                    f"{_fmt_krw(buy_krw)} / 전체 {_fmt_krw(full_krw)} ({ps['position_pct']:.0f}%)\n"
                                    f"(잔여 {100-split_pct:.0f}%는 DCA 대기)")
                                chart = generate_chart(ticker, signal_data[ticker], r)
                                if chart:
                                    send_telegram_photo(chart, f"📥 {name} BUY {_fmt_krw(r['price'])}")
                            else:
                                send_telegram(f"❌ <b>{name}</b> 매수 주문 실패 — 수동 확인 필요")
                    else:
                        signal_fired = True
                        pending_exposure += proposed_pct
                        pending_buy_tickers.append(ticker)
                        print(f"   📋 {name} 매수 신호 ({'장외 — 주문 미실행' if not cb_triggered else '서킷브레이커'})")

        # === 청산 ===
        elif r["signal"] in ["CLOSE", "STRONG_CLOSE"]:
            if ticker in portfolio:
                close_reason = r.get("close_reason", "SIGNAL")
                name         = ticker.replace("KRW-", "")
                vol          = portfolio[ticker].get("volume", 0)
                if can_trade:
                    if has_recent_order(order_log, ticker, "SELL"):
                        print(f"   ℹ️ {name} 최근 {ORDER_COOLDOWN_MINUTES}분 내 매도 주문 — 중복 방지")
                    else:
                        order = execute_sell(ticker, vol)
                        if order:
                            record_order(order_log, ticker, "SELL")
                            signal_fired = True
                            entry_p = portfolio[ticker]["entry_price"]
                            pnl     = (r["price"] / entry_p - 1) * 100 if entry_p > 0 else 0
                            record_trade(ticker, "SELL", r["price"], vol, vol * r["price"], close_reason, entry_p, pnl)
                            # v5.48: 매도 분석 webhook
                            _hold_h = 0
                            try:
                                _ed = portfolio[ticker].get("entry_date", "")
                                if _ed and _ed != "synced":
                                    _edt = datetime.fromisoformat(_ed)
                                    if _edt.tzinfo is None:
                                        _edt = _edt.replace(tzinfo=timezone.utc)
                                    _hold_h = round((utc_now() - _edt).total_seconds() / 3600, 1)
                            except Exception:
                                pass
                            _send_trade_analysis_webhook(
                                ticker, "SELL", r["price"], vol, vol * r["price"],
                                close_reason, entry_p, pnl,
                                extra_data={
                                    "hold_hours": _hold_h,
                                    "entry_rsi": round(r.get("rsi", 0), 1),
                                    "exit_rsi": round(r.get("rsi", 0), 1),
                                    "entry_score": round(r.get("ensemble_score", 0), 1),
                                    "market_regime": _wh_regime, "btc_change_pct": _wh_btc_chg,
                                }
                            )
                            # v3.3 fix: 손실 매도 시 원인 불문 쿨다운 (스탑/시그널/시간 모두)
                            if pnl < 0:
                                order_log[f"{ticker}_STOP_CD"] = utc_now().isoformat()
                                save_order_log(order_log)
                                print(f"   ⏳ {name} 쿨다운 {STOP_COOLDOWN_HOURS}h 설정 (손실 {pnl:+.1f}%)")
                            # v4.0: 매도가 기억 저장 (재매수 가격 게이트)
                            sell_memory = portfolio.get("_sell_memory", {})
                            sell_memory[ticker] = {
                                "price": r["price"],
                                "date": utc_now().isoformat(),
                            }
                            portfolio["_sell_memory"] = sell_memory
                            # 매도 후 포트폴리오/노출/자본 즉시 갱신
                            sold_value = vol * r["price"]
                            del portfolio[ticker]
                            portfolio_tickers.discard(ticker)
                            total_exposure = max(0, total_exposure - sold_value / total_capital)
                            capital += sold_value * (1 - TOTAL_COST_BPS / 10000)
                            send_telegram(
                                f"📤 <b>{name}</b> 매도 주문 접수 ({close_reason})\n"
                                f"{vol} @ {_fmt_krw(r['price'])}\n"
                                f"진입{_fmt_krw(entry_p)} → 현재{_fmt_krw(r['price'])} ({pnl:+.1f}%)\n"
                                f"(체결 확인: 다음 sync)")
                            print(f"   🤖 매도 주문 접수 ({close_reason}): {_fmt_krw(r['price'])}")
                            if ticker in signal_data:
                                chart = generate_chart(ticker, signal_data[ticker], r)
                                if chart:
                                    send_telegram_photo(chart, f"📤 {name} SELL {_fmt_krw(r['price'])}")
                        else:
                            send_telegram(f"❌ <b>{name}</b> 매도 주문 실패 — 수동 확인 필요")
                else:
                    signal_fired = True
                    print(f"   📋 {name} 청산 신호 ({close_reason}) ({'서킷브레이커' if cb_triggered else '알림만'})")

    # 특이사항 알림
    for r in results:
        if r["signal"] == "NO_DATA":
            continue
        if r.get("volume_spike"):
            name = r["ticker"].replace("KRW-", "")
            print(f"   🔊 {name} 거래량 급증 {r['volume_ratio']:.1f}x")
        if r.get("is_surge"):
            name = r["ticker"].replace("KRW-", "")
            print(f"   ⚡ {name} 급{'등' if r['daily_change'] > 0 else '락'} {r['daily_change']:+.1f}%")

    save_portfolio(portfolio)

    # Phase 4: 리포트
    print(f"\n📁 포트폴리오 노출: {total_exposure*100:.1f}%")
    holdings = [k for k in portfolio if k not in ("_meta", "_sell_memory")]
    if holdings:
        print(f"   보유: {[t.replace('KRW-', '') for t in holdings]}")
    else:
        print("   보유 없음")

    # v3.2: VM은 매수/매도 시에만 텔레그램, 리포트는 GitHub Actions(알림 모드)에서만
    if not signal_fired and not AUTO_TRADE_ENABLED:
        status_msg = format_status_message(results, regime_info, fg)
        send_telegram(status_msg)

    print(f"\n✅ Coin Alert 완료: {utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)


if __name__ == "__main__":
    main()
