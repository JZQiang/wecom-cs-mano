# 企业微信智能客服 V4 — 全自动 RPA 系统

**项目名称：智客（SmartServe）**

基于 **mss 截图 + PIL 红点检测 + EasyOCR 文字提取 + DeepSeek API 回复 + pynput 键鼠控制** 的全自包含客服机器人。支持 **企微 MCP 智能表格自动写入**，每一次客户问答自动存档。

## 技术栈

| 模块 | 方案 | 说明 |
|------|------|------|
| 截图 | **mss** | 内存级截图，快速高效 |
| 红点检测 | **PIL 像素扫描** | 扫描红色像素(R>180, G/B<120)后聚类 |
| 文字提取 | **EasyOCR**（增强版） | 自动放大+对比度增强，识别率更高 |
| 气泡判断 | **PIL 右侧50%颜色检测** | 只检右侧50%区域，蓝>5%判蓝泡 |
| @微信检测 | **OCR + 绿色像素兜底** | 绿色badge像素检测，防漏 |
| 键鼠控制 | **pynput** | 剪贴板粘贴 + 回车发送 |
| AI 回复 | **DeepSeek API** | 通过 config / .env 自动读取 Key |
| 智能表格 | **企业微信 MCP** | 客户问题 + AI回复自动写入「客户问题收集表」 |
| 窗口定位 | **AppleScript** | 获取企业微信窗口坐标 |

## 新增功能：智能表格自动写入 📊

每次检测到客户消息并回复后，自动通过企业微信 MCP 将以下内容写入「客户问题收集表」：

| 字段 | 说明 |
|------|------|
| 客户问题 | OCR 识别出的客户消息原文 |
| AI 回复 | DeepSeek 生成的回复内容 |
| 记录时间 | 自动记录时间戳 |

需在 `~/.hermes/.env` 中配置 `WECOM_BOT_ID` 和 `WECOM_SECRET`。

可在 `config.json` 中通过 `smart_sheet.enabled` 开关控制。

## 安装

```bash
pip3 install mss pynput Pillow requests easyocr
```

## 配置

API Key 自动读取优先级：
1. `~/.hermes/.env` 中的 `DEEPSEEK_API_KEY`
2. `~/.hermes/config.yaml` 中的 `api_key` 字段

编辑 `config.json` 可调整检测间隔、企业微信进程名、AI 提示词、智能表格开关等。

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
裁剪聊天区 → 提取底部气泡+昵称区域
        ↓
判断气泡类型（右侧50%蓝检）
        ↓
  蓝泡（AI回复）？──是──→ 跳过
        ↓ 否
OCR 提取文字（放大+对比度增强）
        ↓
检测 @微信 标识（OCR + 绿色像素兜底）
        ↓
DeepSeek API 生成回复
        ↓
pynput 模拟键盘发送消息
        ↓
写入企业微信智能表格「客户问题收集表」📊
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
     (162px)        (252px)          (646px)
```

第三列内部区域：
```
y=0-80      标题区（群名称）
y=80-526    聊天消息区（去掉右侧成员区域162px）
y=526-560   功能栏
y=560-640   输入区
```

## 底部气泡提取逻辑

1. **从底部往上扫描**，找第一个有内容的行（非白像素 > 宽×3%）
2. **找气泡顶部**：连续5行空白 = 消息间隔
3. **往上延伸30px** 包含昵称区域（@微信在昵称左上角）
4. **最小高度保护50px**：太矮的裁剪区域自动补足
5. **蓝色检测**：只扫右侧50%，`b>r+30, b>g+20, b>120`，>5%判蓝泡
6. **OCR增强**：高度<150px时缩放到200px + 1.5倍对比度

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
│   ├── kb_client.py     # 知识库客户端
│   └── build_kb.py      # 知识库构建脚本
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

**智能表格没写入？** 检查 `~/.hermes/.env` 是否配置了 `WECOM_BOT_ID` 和 `WECOM_SECRET`，以及 `config.json` 中 `smart_sheet.enabled` 是否为 `true`。

## 更新日志

### v4.14.0 (2026-05-14)
- ✨ 新增：智能表格自动写入（企微 MCP）
- ✨ 新增：底部气泡最小高度保护改为50px
- 🔧 优化：移除调试截图，日志更干净
- 🔧 优化：气泡区域裁剪逻辑（气泡上方30px）

### v4.13.0 (2026-05-13)
- 🎯 重写：底部灰色气泡提取 + 右侧50%蓝泡检测
- 🔧 修复：EasyOCR 窄高区域识别失败（放大+对比度增强）
- 🎯 新增：绿色像素检测兜底 @微信 识别
