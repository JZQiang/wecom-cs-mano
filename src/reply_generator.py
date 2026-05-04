"""AI 回复生成器 — 调用大模型生成客服回复

支持多个 provider：
- deepseek: OpenAI 兼容 API
- bailian: 阿里云百炼 dashscope SDK
"""

import os
import json
import time
import requests
from typing import Optional


class ReplyGenerator:
    """AI 回复生成器"""

    def __init__(self, config: dict):
        self.config = config
        reply_cfg = config.get("reply", {})
        ai_cfg = config.get("ai", {})

        self.system_prompt = reply_cfg.get(
            "system_prompt",
            "你是企业微信智能客服「快亮家装饰」的AI助手。语气友好专业，简洁高效。"
        )
        self.style = reply_cfg.get("style", "friendly")
        self.provider = ai_cfg.get("provider", "deepseek")
        self.model = ai_cfg.get("model", "deepseek-chat")
        self.api_key_env = ai_cfg.get("api_key_env", "DEEPSEEK_API_KEY")
        self.base_url = ai_cfg.get("base_url", "https://api.deepseek.com/v1")
        self.api_key = self._get_api_key()

    def _get_api_key(self) -> str:
        for name in [self.api_key_env, "DASHSCOPE_API_KEY", "BAILIAN_API_KEY", "DEEPSEEK_API_KEY"]:
            val = os.environ.get(name, "")
            if val:
                return val
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

    def generate(self, customer_name: str, message: str,
                 context: Optional[list] = None) -> Optional[str]:
        """生成回复"""
        if not self.api_key:
            print(f"⚠️ 未设置 API Key（找了 {self.api_key_env} / DASHSCOPE_API_KEY / BAILIAN_API_KEY）")
            return None

        if self.provider in ("deepseek", "openrouter"):
            return self._generate_deepseek(customer_name, message, context)
        elif self.provider == "bailian":
            return self._generate_bailian(customer_name, message, context)
        else:
            print(f"⚠️ 不支持的 AI 提供商: {self.provider}")
            return None

    def _generate_deepseek(self, customer_name: str, message: str,
                           context: Optional[list] = None) -> Optional[str]:
        """通过 DeepSeek 生成回复（OpenAI 兼容 API）"""
        try:
            messages = [{"role": "system", "content": self.system_prompt}]

            if context:
                for msg in context[-6:]:
                    role = "assistant" if msg.get("is_reply") else "user"
                    name = msg.get("sender", "")
                    content = msg.get("content", "")
                    messages.append({
                        "role": role,
                        "content": f"{name}: {content}"
                    })

            messages.append({
                "role": "user",
                "content": f"客户({customer_name})说: {message}\n\n请作为快亮家装饰的客服回复。回复简短专业，不超过100字。"
            })

            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 200,
                },
                timeout=15
            )

            if resp.status_code != 200:
                print(f"⚠️ DeepSeek 回复 API 失败: {resp.status_code} {resp.text[:200]}")
                return None

            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return reply.strip()

        except requests.Timeout:
            print("⚠️ DeepSeek 回复 API 超时")
            return None
        except Exception as e:
            print(f"⚠️ DeepSeek 回复生成异常: {e}")
            return None

    def _generate_bailian(self, customer_name: str, message: str,
                          context: Optional[list] = None) -> Optional[str]:
        """通过阿里云百炼生成回复"""
        try:
            from dashscope import Generation

            messages = [{"role": "system", "content": self.system_prompt}]

            if context:
                for msg in context[-6:]:
                    role = "assistant" if msg.get("is_reply") else "user"
                    name = msg.get("sender", "")
                    content = msg.get("content", "")
                    messages.append({
                        "role": role,
                        "content": f"{name}: {content}"
                    })

            messages.append({
                "role": "user",
                "content": f"客户({customer_name})说: {message}\n\n请作为快亮家装饰的客服回复。回复简短专业，不超过100字。"
            })

            response = Generation.call(
                model=self.model,
                messages=messages,
                api_key=self.api_key,
                result_format="message",
                temperature=0.7,
                max_tokens=200,
            )

            if response.status_code == 200:
                reply = response.output.choices[0].message.content
                return reply.strip()
            else:
                print(f"⚠️ 百炼回复 API 失败: {response.status_code} {response.message}")
                return None

        except ImportError:
            print("⚠️ dashscope 未安装")
            return None
        except Exception as e:
            print(f"⚠️ 百炼回复生成异常: {e}")
            return None
