# 企业微信智能客服 V4 — 全自动 RPA 系统

基于 **mss 截图 + PIL 红点检测 + EasyOCR 文字提取 + DeepSeek API 回复 + pynput 键鼠控制** 的全自包含客服机器人。

监控企业微信外部群聊，自动识别带 `(@微信)` 标识的客户消息并智能回复。不需要外部 cron job 或视觉模型 API。

## 技术栈

| 模块 | 方案 | 说明 |
|------|------|------|
| 截图 | **mss** | 内存级截图，快速高效 |
| 红点检测 | **PIL 像素扫描** | 扫描红色像素(R>180, G/B<120)后聚类 |
| 文字提取 | **EasyOCR** | 本地运行，支持中英文 |
| 键鼠控制 | **pynput** | 剪贴板粘贴 + 回车发送 |
| AI 回复 | **DeepSeek API** | 通过 config 自动读取 Key |
| 窗口定位 | **AppleScript** | 获取企业微信窗口坐标 |

## 安装

```bash
pip3 install mss pynput Pillow requests easyocr
```

## 配置

无需手动设置环境变量。API Key 自动读取优先级：
1. `~/.hermes/.env` 中的 `DEEPSEEK_API_KEY`
2. `~/.hermes/config.yaml` 中的 `api_key` 字段

编辑 `config.json` 可调整检测间隔、企业微信进程名、AI 提示词等。

## 运行

```bash
cd wecom-cs-mano && python3 main.py
```

后台运行：

```bash
nohup python3 main.py > logs/output.log 2>&1 &
```

查看日志：

```bash
tail -f logs/monitor.log
```

停止：

```bash
pkill -f "python3 main.py"
```

## 工作原理

```
每 3 秒截图第二列（群聊列表）
        ↓
PIL 像素扫描检测红色未读圆点
        ↓
  有红点？──否──→ 继续等待
        ↓ 是
去重检查（图片哈希）
        ↓
取最右侧红点 → 点击群聊行
        ↓ 等待 1.5 秒
截图第三列会话窗口
        ↓
EasyOCR 提取文字
        ↓
DeepSeek API 生成回复
        ↓
pynput 模拟键盘发送消息
        ↓
冷却 → 回到监控循环
```

## 企业微信三列布局

```
┌──────────────┬──────────────┬─────────────────────┐
│  第一列       │  第二列       │  第三列              │
│  功能列表     │  群聊列表     │  会话窗口            │
│              │              │                     │
│ 📌外部群聊    │ 🏠施工群 🔴  │ 张三(@微信): 你好   │
│  通讯录       │ 🏠设计群     │  什么时候能来量房？  │
│  工作台       │ 🏠业主群     │                     │
│              │              │  输入框...           │
└──────────────┴──────────────┴─────────────────────┘
    0% ~ 15%      15% ~ 38.7%     38.7% ~ 100%
```

只检测第二列红点，只回复带 `(@微信)` 标识的客户消息。

## 前置条件

- macOS 系统（需要 AppleScript 获取窗口坐标）
- 企业微信已登录，进程名为「企业微信」（中文）
- 已在「外部群聊」视图
- 屏幕录制权限（mss 截图）
- 辅助功能权限（pynput 键鼠）

## 文件结构

```
wecom-cs-mano/
├── main.py             # 主程序（全自动）
├── config.json         # 配置文件
├── SKILL.md            # 技能说明文档
├── README.md           # 本文件
├── requirements.txt    # 依赖清单
├── start.sh            # 启动脚本
├── mano/
│   ├── capture.py      # mss 截图模块
│   └── executor.py     # pynput 键鼠控制
├── src/
│   ├── window_manager.py    # AppleScript 窗口管理
│   ├── vision_analyzer.py   # EasyOCR 文字提取
│   ├── message_detector.py  # 红点检测 + 消息去重
│   ├── reply_generator.py   # DeepSeek API 回复
│   └── wecom_controller.py  # 企业微信操作逻辑
├── scripts/
│   └── kb_client.py     # 知识库客户端
├── knowledge_base/      # 知识库目录
└── logs/
    ├── monitor.log      # 运行日志
    └── screenshots/     # 调试截图
```

## 常见问题

**窗口检测不到？**
```bash
osascript -e 'tell application "System Events" to tell process "企业微信" to if exists window 1 then get {position of window 1, size of window 1}'
```
注意：macOS 版进程名是中文「企业微信」，不是 "WeCom"。

**OCR 乱码？** 确保企业微信窗口在最前，无遮挡。

**回复发不出去？** 脚本采用两次点击策略：先激活会话窗口 → 再点输入框。检查窗口是否最小化。
