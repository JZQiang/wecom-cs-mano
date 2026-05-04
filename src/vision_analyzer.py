"""视觉分析器 — 调用视觉模型分析企业微信截图

支持多个 provider：
- deepseek: OpenAI 兼容 API，用 deepseek-chat（支持图片输入）
- bailian: 阿里云百炼 dashscope SDK
"""

import base64
import io
import json
import os
import time
import requests
from typing import Optional, List, Dict
from PIL import Image

# 视觉分析提示词
VISION_PROMPT = """你是一个企业微信截图分析专家。请分析这张企业微信群聊截图，找出所有可见的消息。

请以 JSON 格式返回，格式如下：
{
  "messages": [
    {
      "sender": "发送者名称",
      "content": "消息内容",
      "type": "customer"  // customer=有(@微信)标识的外部客户, internal=内部成员, system=系统消息
    }
  ],
  "has_external_marker": true/false,
  "note": "其他观察"
}

注意事项：
- (@微信) 标识表示该用户是外部客户，需要回复
- 只有 type 为 "customer" 的消息才是客户消息
- 如果看到 "(@微信)" 字样在发送者名称后面，说明是外部客户
- 忽略系统消息和内部员工消息
- 如果截图没有消息区域或看不清楚，返回空的 messages 列表"""


class VisionAnalyzer:
    """视觉分析器"""

    def __init__(self, config: dict):
        self.config = config
        vision_cfg = config.get("vision", {})
        self.provider = vision_cfg.get("provider", "deepseek")
        self.model = vision_cfg.get("model", "deepseek-chat")
        self.api_key_env = vision_cfg.get("api_key_env", "DEEPSEEK_API_KEY")
        self.base_url = vision_cfg.get("base_url", "https://api.deepseek.com/v1")
        self.rate_limit = vision_cfg.get("rate_limit_seconds", 3)

        self._last_call_time = 0
        self._api_key = self._get_api_key()

        if not self._api_key:
            print(f"⚠️ 未设置 API Key（找了环境变量 / ~/.hermes/config.yaml），视觉分析将不可用")

    def _get_api_key(self) -> str:
        """从多个来源获取 API Key：环境变量 → Hermes config.yaml"""
        # 先试环境变量
        for name in [self.api_key_env, "DASHSCOPE_API_KEY", "BAILIAN_API_KEY", "DEEPSEEK_API_KEY"]:
            val = os.environ.get(name, "")
            if val:
                return val

        # 从 Hermes config.yaml 读取
        try:
            config_paths = [
                os.path.expanduser("~/.hermes/config.yaml"),
                os.path.expanduser("~/.hermes/config.yml"),
            ]
            for cp in config_paths:
                if os.path.exists(cp):
                    with open(cp) as f:
                        for line in f:
                            if line.strip().startswith("api_key:"):
                                key = line.split(":", 1)[1].strip().strip('"').strip("'")
                                if key:
                                    return key
        except Exception:
            pass

        return ""

    def analyze(self, image: Image.Image) -> List[Dict]:
        """分析截图，提取消息"""
        elapsed = time.time() - self._last_call_time
        if elapsed < self.rate_limit:
            wait = self.rate_limit - elapsed
            print(f"⏳ 视觉分析限流中，等待 {wait:.1f}s...")
            time.sleep(wait)

        self._last_call_time = time.time()

        if self.provider in ("deepseek", "openrouter"):
            return self._analyze_deepseek(image)
        elif self.provider == "bailian":
            return self._analyze_bailian(image)
        else:
            print(f"⚠️ 不支持的视觉提供商: {self.provider}")
            return []

    def _analyze_deepseek(self, image: Image.Image) -> List[Dict]:
        """通过 DeepSeek 视觉模型分析（OpenAI 兼容 API）"""
        if not self._api_key:
            return []

        try:
            # 图片转 base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            data_url = f"data:image/png;base64,{img_b64}"

            # 估算 token 用量（图片 base64 约 data_url 长度的 1/4）
            img_size_kb = len(img_b64) * 3 // 4 // 1024
            print(f"📸 视觉分析中（图片 ~{img_size_kb}KB）...")

            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": VISION_PROMPT}
                        ]
                    }],
                    "temperature": 0.1,
                    "max_tokens": 1024
                },
                timeout=30
            )

            if resp.status_code != 200:
                print(f"⚠️ DeepSeek 视觉 API 失败: {resp.status_code} {resp.text[:200]}")
                return []

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_vision_response(content)

        except requests.Timeout:
            print("⚠️ DeepSeek 视觉 API 超时")
            return []
        except Exception as e:
            print(f"⚠️ DeepSeek 视觉分析异常: {e}")
            return []

    def _analyze_bailian(self, image: Image.Image) -> List[Dict]:
        """通过阿里云百炼视觉模型分析"""
        try:
            from dashscope import MultiModalConversation

            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            messages = [{
                "role": "user",
                "content": [
                    {"image": f"data:image/png;base64,{img_b64}"},
                    {"text": VISION_PROMPT},
                ]
            }]

            response = MultiModalConversation.call(
                model=self.model,
                messages=messages,
                api_key=self._api_key,
                result_format="message"
            )

            if response.status_code != 200:
                print(f"⚠️ 百炼视觉API失败: {response.status_code} {response.message}")
                return []

            content = response.output.choices[0].message.content
            text = ""
            if isinstance(content, list):
                for item in content:
                    if item.get("text"):
                        text += item["text"]
            else:
                text = str(content)

            return self._parse_vision_response(text)

        except ImportError:
            print("⚠️ dashscope 未安装")
            return []
        except Exception as e:
            print(f"⚠️ 百炼视觉分析异常: {e}")
            return []

    def _parse_vision_response(self, text: str) -> List[Dict]:
        """解析视觉模型返回的 JSON"""
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            else:
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    json_str = text[start:end + 1]
                else:
                    print(f"⚠️ 无法解析视觉返回: {text[:200]}...")
                    return []

            data = json.loads(json_str)
            messages = data.get("messages", [])
            for m in messages:
                if "type" not in m:
                    m["type"] = "unknown"
            return messages

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析失败: {e}")
            return []
        except Exception as e:
            print(f"⚠️ 解析视觉返回异常: {e}")
            return []
