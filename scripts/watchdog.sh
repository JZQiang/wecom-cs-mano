#!/bin/bash
# Watchdog for wecom-cs-mano — 每分钟检查进程健康状态
# 如果 heartbeat 超过 60 秒未更新或进程挂了，自动重启
#
# 安装（添加 crontab）：
#   crontab -e
#   * * * * * ~/.hermes/workspace/skills/wecom-cs-mano/scripts/watchdog.sh

DIR="$(cd "$(dirname "$0")/.." && pwd)"
HEALTH_FILE="$DIR/logs/health.json"
PID_FILE="$DIR/logs/pid.txt"
LOG_FILE="$DIR/logs/watchdog.log"

# 日志函数
log() {
    echo "[watchdog] $(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

# 检查 health 文件是否存在且新鲜
if [ -f "$HEALTH_FILE" ]; then
    # macOS stat
    MTIME=$(stat -f "%m" "$HEALTH_FILE" 2>/dev/null)
    NOW=$(date +%s)
    AGE=$((NOW - MTIME))

    if [ "$AGE" -lt 60 ]; then
        # health 文件新鲜，检查进程是否真正存活
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE" 2>/dev/null)
            if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
                # 一切正常
                exit 0
            fi
        fi
        log "⚠️ health 文件新鲜但进程不存在，准备重启"
    else
        log "⚠️ health 文件过期 (${AGE}s)，准备重启"
    fi
else
    log "⚠️ health 文件不存在，准备启动"
fi

# 进程异常 → 重启
cd "$DIR" || exit 1

# 杀死旧进程（如果有 pid 文件但进程还在）
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ]; then
        kill "$OLD_PID" 2>/dev/null
        sleep 2
    fi
fi

# 启动新进程
nohup python3 main.py >> logs/output.log 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
log "✅ 已重启，新 PID: $NEW_PID"
