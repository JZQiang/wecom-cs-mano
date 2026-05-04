"""消息检测器 — 视觉分析 + 消息去重"""

import json
import os
import time
import hashlib
from typing import List, Optional, Dict
from datetime import datetime
from PIL import Image


class MessageDetector:
    """企业微信消息检测器

    通过视觉模型分析截图，检测新消息和(@微信)客户标识
    """

    def __init__(self, config: dict, vision_callback=None):
        """
        Args:
            config: 配置字典
            vision_callback: 视觉分析回调函数
                            async def analyze(image) -> List[dict]
        """
        self.config = config
        self.marker = config.get("external_user_marker", "@微信")
        dedup_cfg = config.get("deduplication", {})
        self.dedup_enabled = dedup_cfg.get("enabled", True)
        self.dedup_window = dedup_cfg.get("window_seconds", 60)

        # 视觉分析回调
        self.vision_callback = vision_callback

        # 状态管理
        self._seen_messages: Dict[str, float] = {}  # hash -> timestamp
        self._last_analysis_result: List[dict] = []
        self._last_analysis_time = 0
        self._stats = {
            "total_checks": 0,
            "messages_found": 0,
            "replies_sent": 0,
            "last_message_time": None,
        }

    def analyze_screenshot(self, screenshot: Image.Image) -> List[dict]:
        """分析截图，提取消息

        Args:
            screenshot: 窗口截图 PIL Image

        Returns:
            消息列表，每项包含:
            - type: "customer" / "internal" / "system"
            - sender: 发送者名称
            - content: 消息内容
            - is_new: 是否为新消息
            - position: 在截图中的位置信息
        """
        self._stats["total_checks"] += 1

        if not self.vision_callback:
            print("⚠️ 未设置视觉分析回调")
            return []

        # 调用视觉模型分析
        messages = self.vision_callback(screenshot)

        # 标记新消息
        for msg in messages:
            msg_hash = self._message_hash(msg)
            msg["hash"] = msg_hash
            msg["is_new"] = self._is_new_message(msg_hash)

            if msg["is_new"]:
                self._seen_messages[msg_hash] = time.time()
                self._stats["messages_found"] += 1
                self._stats["last_message_time"] = datetime.now().isoformat()

        self._cleanup_old_hashes()
        self._last_analysis_result = messages
        self._last_analysis_time = time.time()

        return messages

    def get_new_customer_messages(self) -> List[dict]:
        """获取新的客户消息（(@微信)标识的新消息）

        Returns:
            新客户消息列表
        """
        customer_msgs = [
            m for m in self._last_analysis_result
            if m.get("type") == "customer" and m.get("is_new")
        ]
        return customer_msgs

    def get_all_customer_messages(self) -> List[dict]:
        """获取所有客户消息（含已读的）"""
        return [
            m for m in self._last_analysis_result
            if m.get("type") == "customer"
        ]

    def has_new_customer_message(self) -> bool:
        """是否有新客户消息"""
        return len(self.get_new_customer_messages()) > 0

    def mark_replied(self, message: dict):
        """标记消息已回复"""
        if "hash" in message:
            self._stats["replies_sent"] += 1

    def _message_hash(self, msg: dict) -> str:
        """生成消息唯一哈希（用于去重）

        基于发送者 + 内容 + 大致时间生成
        """
        key = f"{msg.get('sender', '')}:{msg.get('content', '')}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _is_new_message(self, msg_hash: str) -> bool:
        """判断消息是否为新消息（未在去重窗口内出现过）"""
        if not self.dedup_enabled:
            return True

        if msg_hash in self._seen_messages:
            elapsed = time.time() - self._seen_messages[msg_hash]
            return elapsed > self.dedup_window

        return True

    def _cleanup_old_hashes(self):
        """清理过期的去重记录"""
        if not self.dedup_enabled:
            return

        now = time.time()
        expire = self.dedup_window * 2  # 保留双倍窗口
        expired = [
            h for h, t in self._seen_messages.items()
            if now - t > expire
        ]
        for h in expired:
            del self._seen_messages[h]

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self._stats,
            "seen_messages_count": len(self._seen_messages),
            "last_analysis_seconds_ago": (
                time.time() - self._last_analysis_time
                if self._last_analysis_time else None
            ),
        }

    def save_stats(self, stats_file: str):
        """保存统计信息到文件"""
        try:
            os.makedirs(os.path.dirname(stats_file), exist_ok=True)
            with open(stats_file, "w") as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存统计信息失败: {e}")

    def reset(self):
        """重置检测器状态"""
        self._seen_messages.clear()
        self._last_analysis_result = []
        self._last_analysis_time = 0
