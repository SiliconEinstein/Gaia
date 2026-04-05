#!/usr/bin/env bash
# Bulk import loop: local import → upload S3 → cleanup → repeat
#
# Usage:
#   bash scripts/bulk-import-loop.sh
#
# Environment:
#   LOCAL_DB      — local LanceDB path (default: /data/lancedb/lkm-bulk)
#   S3_URI        — remote S3 URI (default: s3://datainfra-test/gaia_server_test)
#   OUTPUT_DIR    — checkpoint/log dir (default: ./output/import-287k)
#   MAX_PAPERS    — total papers to import (default: 300000)
#   DISK_LIMIT_GB — stop importing when free disk drops below this (default: 10)
#   CHUNK_SIZE    — papers per chunk (default: 1000)

set -euo pipefail

LOCAL_DB="${LOCAL_DB:-/data/lancedb/lkm-bulk}"
S3_URI="${S3_URI:-s3://datainfra-test/gaia_server_test}"
OUTPUT_DIR="${OUTPUT_DIR:-./output/import-287k}"
MAX_PAPERS="${MAX_PAPERS:-300000}"
DISK_LIMIT_GB="${DISK_LIMIT_GB:-10}"
CHUNK_SIZE="${CHUNK_SIZE:-1000}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

free_gb() {
    df -BG "${LOCAL_DB%/*}" 2>/dev/null | awk 'NR==2{print int($4)}' \
    || df -g "${LOCAL_DB%/*}" 2>/dev/null | awk 'NR==2{print $4}'
}

checkpoint_count() {
    python3 -c "
import json, sys
try:
    d = json.load(open('${OUTPUT_DIR}/checkpoint.json'))
    print(sum(1 for v in d.values() if v == 'ingested'))
except FileNotFoundError:
    print(0)
" 2>/dev/null
}

round=0

while true; do
    round=$((round + 1))
    ingested=$(checkpoint_count)
    log "══ Round $round | Already ingested: $ingested ══"

    # Phase 1: Import to local LanceDB
    log "Phase 1: Importing to local ($LOCAL_DB)..."
    uv run python -m gaia.lkm.pipelines.import_lance \
        --lkm-db-uri "$LOCAL_DB" \
        --output-dir "$OUTPUT_DIR" \
        --max-papers "$MAX_PAPERS" \
        --chunk-size "$CHUNK_SIZE" \
        || true  # don't exit on Ctrl+C or error

    new_ingested=$(checkpoint_count)
    imported=$((new_ingested - ingested))
    log "Phase 1 done: imported $imported papers this round (total: $new_ingested)"

    if [ "$imported" -eq 0 ]; then
        log "No new papers imported — all done!"
        break
    fi

    # Phase 2: Upload to S3
    log "Phase 2: Uploading to S3 ($S3_URI)..."
    uv run python -m gaia.lkm.pipelines.import_lance upload \
        --local-path "$LOCAL_DB" \
        --s3-uri "$S3_URI" \
        --append

    log "Phase 2 done: uploaded to S3"

    # Phase 3: Cleanup local data
    log "Phase 3: Cleaning up local data..."
    rm -rf "$LOCAL_DB"
    log "Phase 3 done: freed $(free_gb)GB disk"
done

log "Import complete! Total ingested: $(checkpoint_count)"
