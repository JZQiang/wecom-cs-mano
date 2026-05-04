"""企业微信 GUI 控制器 — 通过键鼠模拟操作企业微信客户端"""

import time
import subprocess
import platform
from typing import Optional, Tuple

from mano.executor import ActionExecutor


class WeComController:
    """企业微信 GUI 控制器

    通过键鼠模拟操作企业微信：
    - 点击输入框
    - 粘贴回复内容
    - 发送消息
    """

    # 企业微信输入框在窗口中的相对位置（比例）
    # 这些值需要根据实际屏幕校准
    INPUT_BOX_RATIO = {"x": 0.05, "y": 0.88, "width": 0.70, "height": 0.05}
    SEND_BUTTON_RATIO = {"x": 0.80, "y": 0.88}

    def __init__(self, config: dict):
        self.config = config
        self.executor = ActionExecutor()
        self.process_name = config.get("wecom_process_name", "WeCom")

    def focus_window(self):
        """将企业微信窗口置于前台并激活"""
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "{self.process_name}" to activate'],
                timeout=5, capture_output=True
            )
            time.sleep(0.8)  # 等待窗口激活
        except Exception as e:
            print(f"⚠️ 激活窗口失败: {e}")

    def click_input_box(self, wecom_region: Tuple[int, int, int, int]):
        """点击输入框

        Args:
            wecom_region: (left, top, width, height) 窗口位置
        """
        left, top, width, height = wecom_region
        ratio = self.INPUT_BOX_RATIO

        x = left + int(width * ratio["x"])
        y = top + int(height * ratio["y"])

        self.executor.move_to(x, y, duration=0.3)
        time.sleep(0.2)
        self.executor.click(x, y)
        time.sleep(0.3)

    def type_and_send(self, text: str, wecom_region: Tuple[int, int, int, int]):
        """在输入框输入文本并发送

        Args:
            text: 要发送的文本
            wecom_region: (left, top, width, height) 窗口位置
        """
        # 1. 确保窗口在前台
        self.focus_window()

        # 2. 点击输入框
        self.click_input_box(wecom_region)

        # 3. 清空输入框（全选+删除）
        self.executor.hotkey("cmd", "a")
        time.sleep(0.1)

        # 4. 输入回复内容（剪贴板粘贴）
        self.executor.type_text(text)
        time.sleep(0.2)

        # 5. 按回车发送
        self.executor.press_key("enter")
        time.sleep(0.5)

    def scroll_chat_area(self, wecom_region: Tuple[int, int, int, int],
                         direction: str = "down", amount: int = 5):
        """滚动聊天区域

        Args:
            wecom_region: 窗口位置
            direction: "up" / "down"
            amount: 滚动量
        """
        left, top, width, height = wecom_region
        x = left + width // 2
        y = top + height // 2

        clicks = amount if direction == "up" else -amount
        self.executor.scroll(clicks, x, y)

    def is_chat_active(self, wecom_region: Tuple[int, int, int, int]) -> bool:
        """检查聊天区域是否活跃（有输入框）

        通过检测输入框位置的元素是否存在

        Args:
            wecom_region: 窗口位置
        """
        # 简化实现：检查窗口大小是否正常
        _, _, width, height = wecom_region
        return width > 200 and height > 200
