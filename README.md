# 企业微信智能客服（mano-skill 重构版）

基于 mss + 视觉模型 + pynput 的 RPA 客服系统。

## 安装

```bash
pip3 install -r requirements.txt
```

## 配置

1. 设置阿里云百炼 API Key：
```bash
export DASHSCOPE_API_KEY="your-api-key"
```

2. 编辑 `config.json` 按需调整。

## 运行

```bash
python3 main.py
```

## 后台运行

```bash
./start.sh
```

## 依赖

- mss — 屏幕截图
- pynput — 键鼠控制
- dashscope — 阿里云百炼 API
- Pillow — 图像处理
