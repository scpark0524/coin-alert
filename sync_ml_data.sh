#!/bin/bash
# ML 데이터 로컬 동기화 — 트레이딩 VM → 로컬
# 사용: bash sync_ml_data.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SSH_KEY="$SCRIPT_DIR/ssh-key-2026-02-25.key"
VM_HOST="opc@158.179.171.23"
VM_DIR="/home/opc/coin-alert"
LOCAL_DIR="$SCRIPT_DIR/data"

mkdir -p "$LOCAL_DIR"

echo "=== ML 데이터 동기화 ==="
echo "VM: $VM_HOST:$VM_DIR → 로컬: $LOCAL_DIR"
echo ""

# 1. ml_features.jsonl 동기화
echo "[1/3] ml_features.jsonl 동기화..."
scp -i "$SSH_KEY" "$VM_HOST:$VM_DIR/ml_features.jsonl" "$LOCAL_DIR/ml_features.jsonl"

# 2. trade_history.json 동기화
echo "[2/3] trade_history.json 동기화..."
scp -i "$SSH_KEY" "$VM_HOST:$VM_DIR/trade_history.json" "$LOCAL_DIR/trade_history.json" 2>/dev/null || echo "  (없음 — 스킵)"

# 3. 날짜별 스냅샷 보관 (덮어쓰기 방지)
TODAY=$(date +%Y-%m-%d)
SNAPSHOT="$LOCAL_DIR/snapshots"
mkdir -p "$SNAPSHOT"
if [ -f "$LOCAL_DIR/ml_features.jsonl" ]; then
    cp "$LOCAL_DIR/ml_features.jsonl" "$SNAPSHOT/ml_features_${TODAY}.jsonl"
    echo "[3/3] 스냅샷 저장: ml_features_${TODAY}.jsonl"
fi

# 4. 요약
echo ""
LINES=$(wc -l < "$LOCAL_DIR/ml_features.jsonl" | tr -d ' ')
SIZE=$(ls -lh "$LOCAL_DIR/ml_features.jsonl" | awk '{print $5}')
FIRST=$(head -1 "$LOCAL_DIR/ml_features.jsonl" | python3 -c "import json,sys; print(json.load(sys.stdin).get('timestamp','?')[:10])" 2>/dev/null || echo "?")
LAST=$(tail -1 "$LOCAL_DIR/ml_features.jsonl" | python3 -c "import json,sys; print(json.load(sys.stdin).get('timestamp','?')[:10])" 2>/dev/null || echo "?")

echo "=== 동기화 완료 ==="
echo "  레코드: ${LINES}건 (${SIZE})"
echo "  기간: ${FIRST} ~ ${LAST}"

# 스냅샷 정리 (30일 이상 삭제)
find "$SNAPSHOT" -name "ml_features_*.jsonl" -mtime +30 -delete 2>/dev/null
SNAP_COUNT=$(ls "$SNAPSHOT"/ml_features_*.jsonl 2>/dev/null | wc -l | tr -d ' ')
echo "  스냅샷: ${SNAP_COUNT}개 보관 중"
