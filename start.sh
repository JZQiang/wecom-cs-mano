#!/bin/bash
# 企业微信客服监控（轻量版）— 启动脚本
# 不需要 API Key，AI 回复由 Hermes Agent（视觉分析）处理

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 检测可用的 Python
PYTHON=""
for py in /usr/bin/python3 /Users/kuailiangjia-it/.hermes/hermes-agent/venv/bin/python3 $(which python3 2>/dev/null); do
    if [ -x "$py" ]; then
        if $py -c "import mss, pynput, PIL" 2>/dev/null; then
            PYTHON="$py"
            echo "🔍 使用 Python: $($py --version)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ 未找到可用的 Python 环境（需安装 mss, pynput, Pillow）"
    echo "   请执行: pip3 install mss pynput Pillow"
    exit 1
fi

echo "🚀 启动企业微信客服监控..."
mkdir -p logs

# 后台运行
nohup $PYTHON main.py > logs/output.log 2>&1 &
PID=$!
echo $PID > logs/pid.txt

echo ""
echo "✅ 客服监控已启动 (PID: $PID)"
echo "   Python: $($PYTHON --version)"
echo "   日志: logs/monitor.log"
echo "   输出: logs/output.log"
echo ""
echo "📋 常用命令:"
echo "   查看实时日志:  tail -f logs/monitor.log"
echo "   停止服务:      kill \$(cat logs/pid.txt)"
echo ""
echo "💡 AI 回复由 Hermes Agent 自动处理"
echo "   Hermes 会每分钟检查一次是否有新消息"
echo "   （使用 Gemini Flash 视觉模型分析截图）"
