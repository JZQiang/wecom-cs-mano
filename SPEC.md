# 企业微信智能客服 — 项目交接文档

## 项目概况

全自动企微客服系统：监控企业微信外部群聊，自动回复 @微信 客户的提问。

**技术路线：** RPA 方案（mss 截图 + PIL 像素检测 + EasyOCR + DeepSeek API + pynput 键鼠模拟）
**项目路径：** `~/.hermes/workspace/skills/wecom-cs-mano/`

## 当前状态（2026-05-13 最新改版）

### 已修复的问题

1. **蓝色气泡过滤** ✅ — `_remove_blue_bubbles()` OCR 前把蓝色像素涂白，避免 AI 自己的历史回复被识别为客户消息
2. **内部成员过滤** ✅ — AI prompt 中明确要求忽略内部成员消息，靠 @微信 绿色标识做开关
3. **全宽截图** ✅ — 不再裁剪左 35%，截取聊天消息区全部宽度，避免客户长消息越界

### 核心逻辑

```
循环 3 秒:
  1. 截图群聊列表 → PIL 红点检测
  2. 有红点 → 点击进入该群聊
  3. 截图全宽聊天区（去顶去底）
  4. 去蓝色气泡（涂白 AI 自己发的）
  5. EasyOCR 提取文字
  6. 检测 @微信（OCR 文字 + 绿色像素兜底）
  7. 有绿色标识 → 全量文本喂 DeepSeek → 生成回复
  8. pynput 打字发送
```

### 文件结构

```
main.py                 853行 — 主程序（全流程自包含）
mano/
  capture.py             68行 — mss 截图模块
  executor.py           202行 — pynput 键鼠控制
scripts/kb_client.py    237行 — 知识库 TF-IDF 检索
src/
  vision_analyzer.py    230行 — 视觉分析（备用，未启用）
  reply_generator.py    166行 — 回复生成器
  window_manager.py     136行 — 窗口管理
  message_detector.py   170行 — 消息检测
  wecom_controller.py   110行 — 企微控制器
config.json              — 配置文件（AI Key/模型/提示词）
requirements.txt         — 依赖清单
test_questions.md        — 测试问题集
```

## 要改的内容（给 Claude Code 的任务）

### 1. 代码重构（核心任务）

main.py 853 行太长了，拆成模块：
- 把红点检测、OCR、AI 回复、消息发送拆到 `src/` 下已有模块中
- 保持全流程在一个入口文件，但逻辑分模块调用
- `mano/` 下的 capture 和 executor 保持不动

### 2. @微信 绿色 badge 检测优化

当前 `_has_green_badge()` 靠绿色像素聚类检测，问题：
- 绿色像素阈值 g > 130, g > r*1.4, g > b*1.4 可能误判
- 不同聊天背景色下可能有偏差
- 建议：用更精确的 HSV 色彩空间检测，或调参提高准确率

### 3. OCR 准确率

EasyOCR 对聊天消息识别率不高，导致答非所问。方向：
- 考虑用 PaddleOCR 替代（已安装 paddleocr）
- 或增加 OCR 后处理（纠错、格式化）

### 4. 知识库增强

已有 TF-IDF 知识库（`scripts/kb_client.py`），但：
- 知识库内容需补充完整
- 可考虑升级为向量数据库/embedding 方案

### 5. crash 恢复

当前进程可能 hang，需加：
- 看门狗机制（定期检查日志时间戳）
- 崩溃自动重启
- 健康检查 HTTP endpoint

## 技术细节

### 窗口布局（1298×640 窗口）

| 列 | x% | width% | 内容 |
|---|-----|--------|------|
| 第一列 | 0% | 7% | 功能列表 |
| 第二列 | 15% | 23.7% | 群聊列表 |
| 第三列 | 38.7% | 61.3% | 会话窗口 |

### 红点检测参数

- 红色: R > 180, G/B < 120
- 最小连续像素: 3px
- 检测区域: 第二列全高

### OCR 预处理

1. 裁剪: (0, 6%h, 全宽, 85%h) — 去掉顶部标题和底部输入框
2. 去蓝色气泡: 蓝色像素 B > R+30, B > G+20, B > 140 → 涂白
3. 直接 EasyOCR 识别

### AI Prompt（重要）

System prompt = 快亮家涂装客服身份
User prompt = OCR 文本 + 指令（识别@微信客户提问、忽略系统通知、忽略内部成员消息、忽略 AI 历史回复）

### 依赖

```
pip install mss pynput Pillow requests easyocr
```

macOS 权限：屏幕录制 + 辅助功能

## 启动方式

```bash
cd ~/.hermes/workspace/skills/wecom-cs-mano
python3 main.py
```

## 项目名字

wecom-cs-mano（wecom = 企业微信, cs = customer service, mano = 手工/手动操作）
