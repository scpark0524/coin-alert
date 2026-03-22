#!/bin/bash
# coin_alert.py 배포 스크립트 — 트레이딩 VM (158.179.171.23)
# 이 스크립트만 사용할 것. 수동 scp/rsync 금지.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SSH_KEY="$SCRIPT_DIR/ssh-key-2026-02-25.key"
VM_HOST="opc@158.179.171.23"
VM_DIR="/home/opc/coin-alert"

echo "=== coin-alert 배포 시작 ==="
echo "대상: $VM_HOST:$VM_DIR"
echo ""

# 1. 문법 검증
echo "[1/5] 문법 검증..."
python3 -c "import py_compile; py_compile.compile('$SCRIPT_DIR/coin_alert.py', doraise=True)" || exit 1
echo "  OK"

# 2. 배포
echo "[2/5] 파일 전송..."
scp -i "$SSH_KEY" "$SCRIPT_DIR/coin_alert.py" "$VM_HOST:$VM_DIR/"
if [ -f "$SCRIPT_DIR/trade_model.py" ]; then
    scp -i "$SSH_KEY" "$SCRIPT_DIR/trade_model.py" "$VM_HOST:$VM_DIR/"
fi
echo "  OK"

# 3. pycache 삭제
echo "[3/5] pycache 삭제..."
ssh -i "$SSH_KEY" "$VM_HOST" "rm -rf $VM_DIR/__pycache__"
echo "  OK"

# 4. 해시 검증
echo "[4/5] 해시 검증..."
LOCAL_HASH=$(md5 -q "$SCRIPT_DIR/coin_alert.py" 2>/dev/null || md5sum "$SCRIPT_DIR/coin_alert.py" | cut -d' ' -f1)
VM_HASH=$(ssh -i "$SSH_KEY" "$VM_HOST" "md5sum $VM_DIR/coin_alert.py | cut -d' ' -f1")
echo "  로컬: $LOCAL_HASH"
echo "  VM:   $VM_HASH"
if [ "$LOCAL_HASH" != "$VM_HASH" ]; then
    echo "  ❌ 해시 불일치! 배포 실패."
    exit 1
fi
echo "  ✅ 해시 일치"

# 5. 핵심 기능 존재 확인
echo "[5/5] 핵심 기능 확인..."
ssh -i "$SSH_KEY" "$VM_HOST" "cd $VM_DIR && \
    echo \"  버전: \$(head -2 coin_alert.py | tail -1)\" && \
    echo \"  webhook: \$(grep -c '_send_trade_analysis_webhook' coin_alert.py)개\" && \
    echo \"  분할SL: \$(grep -c 'PARTIAL_SL_ENABLED' coin_alert.py)개\" && \
    echo \"  백분위필터: \$(grep -c 'ENTRY_PERCENTILE_MAX' coin_alert.py)개\" && \
    echo \"  리스크레벨: \$(grep -c 'RISK_LEVEL' coin_alert.py)개\""

echo ""
echo "=== 배포 완료 ==="
