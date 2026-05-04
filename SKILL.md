---
name: wecom-cs-mano
description: "企业微信智能客服 V4（全自动版）- mss截图 + PIL红点检测 + EasyOCR + DeepSeek AI + pynput打字，全自包含无需外部API视觉模型"
version: 4.4.0
icon: 🤖
metadata:
  author: "惊蛰"
  replaces: "wecom-rpa-customer-service"
---

# 企业微信智能客服 V4（全自动版）

**监控企业微信外部群聊，自动回复带 (@微信) 标识的客户消息**

基于 **mss 截图 + PIL 像素红点检测 + EasyOCR 文字提取 + DeepSeek AI 回复 + pynput 键鼠控制**，全自包含，不需要外部视觉模型 API。

## 技术栈

| 模块 | 方案 | 说明 |
|------|------|------|
| 截图 | **mss** | 内存级截图，快速 |
| 红点检测 | **PIL 像素扫描** | 扫描红色像素(R>180, G/B<120)后聚类，无需视觉模型 |
| 文字提取 | **EasyOCR** | 本地运行，支持中英文 |
| 键鼠控制 | **pynput** | 剪贴板粘贴 + 回车发送 |
| AI 回复 | **DeepSeek API** | 调用 DeepSeek Chat |
| 窗口定位 | **AppleScript** | 获取企业微信窗口位置 |

**注意：本系统不依赖百炼/阿里云 API，你不需要百炼的 Key。**

## 快速开始

### 1. 安装依赖

```bash
cd skills/wecom-cs-mano
pip3 install mss pynput Pillow requests easyocr
```

### 2. 设置 API Key

AI 回复使用的是 DeepSeek API。自动读取优先级：
1. `~/.hermes/.env` 中的 `DEEPSEEK_API_KEY`
2. `~/.hermes/config.yaml` 中的 `api_key` 字段

无需手动设置环境变量。

### 3. 授予权限

首次运行需要授予：
- **屏幕录制权限** - 系统设置 → 隐私与安全性 → 屏幕录制 → 添加终端/Python
- **辅助功能权限** - 系统设置 → 隐私与安全性 → 辅助功能 → 添加终端/Python

### 4. 启动

```bash
cd ~/.hermes/workspace/skills/wecom-cs-mano
python3 main.py
```

### 5. 后台运行

```bash
nohup python3 main.py > logs/output.log 2>&1 &
```

## 文件结构

```
wecom-cs-mano/
├── main.py             # 主程序（全自动）
├── config.json         # 配置文件
├── SKILL.md            # 技能说明
├── README.md           # 使用说明
├── start.sh            # 启动脚本
├── requirements.txt    # 依赖清单
├── mano/
│   ├── __init__.py
│   ├── capture.py      # mss 截图模块
│   └── executor.py     # pynput 键鼠控制
├── src/
│   ├── window_manager.py   # AppleScript 窗口管理
│   ├── vision_analyzer.py  # OCR 文字提取（EasyOCR）
│   ├── message_detector.py # 消息检测 + 红点检测
│   ├── reply_generator.py  # AI 回复生成（DeepSeek API）
│   └── wecom_controller.py # 企业微信操作逻辑
├── scripts/
│   └── kb_client.py        # 知识库客户端
├── knowledge_base/         # 知识库目录
└── logs/
    ├── monitor.log         # 运行日志
    └── screenshots/        # 调试截图
```

## 配置文件 (`config.json`)

```json
{
  "check_interval_seconds": 3,
  "wecom_process_name": "企业微信",
  "logging": {
    "log_file": "logs/monitor.log"
  },
  "ai": {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "base_url": "https://api.deepseek.com",
    "api_key": "",
    "system_prompt": "你是企业微信智能客服「快亮家装饰」的AI助手。语气友好专业，简洁高效。回复不超过100字。只回复带有「(@微信)」标识的客户消息。"
  }
}
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `check_interval_seconds` | 截图检测间隔 | 3 秒 |
| `wecom_process_name` | 企业微信进程名（中文） | "企业微信" |
| `ai.api_key` | 留空自动从 Hermes config 读取 | "" |
| `ai.model` | AI 模型 | deepseek-chat |
| `ai.system_prompt` | 系统提示词 | 见上 |

## 工作流程

```
每3秒截图第二列（群聊列表）
        ↓
PIL 像素扫描检测红色未读圆点
        ↓
  有红点？──否──→ 继续等待
        ↓ 是
去重检查（图片哈希，防重复处理）
        ↓
取最右侧红点 → 点击群聊行（红点左偏移）
        ↓ 等待1.5秒
截图第三列（会话窗口）
        ↓
EasyOCR 提取文字（注意：需传 numpy array）
        ↓
DeepSeek API 生成回复（AI 自动识别 @微信 客户消息）
        ↓
pynput 发送回复：
  ① 先点第三列中间 (x=50%, y=40%) 激活会话窗口
  ② 再点输入框 (x=40%, y=90%)
  ③ 粘贴文本 → 回车发送
        ↓
冷却 → 回到监控循环
```

## 已知限制

- 企业微信窗口不能最小化（需可见）
- 需要屏幕录制权限 + 辅助功能权限
- 红点检测对主题颜色敏感（深色/浅色主题可能需要调参）
- 每次只处理最右侧红点对应的群聊
- AI 回复需要网络连接（调用 DeepSeek API）
