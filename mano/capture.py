"""截图工具 — 基于 mss（复用 mano-skill 方案）"""

import mss
import mss.tools
from PIL import Image
from typing import Optional, Tuple


def capture_screen(region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
    """截取屏幕或指定区域

    Args:
        region: (left, top, width, height) 可选区域

    Returns:
        PIL Image
    """
    with mss.mss() as sct:
        if region:
            monitor = {"left": region[0], "top": region[1],
                       "width": region[2], "height": region[3]}
        else:
            monitor = sct.monitors[1]  # 主屏幕

        screenshot = sct.grab(monitor)
        return Image.frombytes("RGB", screenshot.size, screenshot.rgb)


def capture_wecom_window(wecom_region: Tuple[int, int, int, int]) -> Image.Image:
    """截取企业微信窗口指定区域

    Args:
        wecom_region: (left, top, width, height) 窗口位置

    Returns:
        窗口截图 PIL Image
    """
    return capture_screen(wecom_region)


def capture_message_area(wecom_region: Tuple[int, int, int, int],
                         ratio: dict) -> Image.Image:
    """截取消息区域（窗口内部的消息列表部分）

    Args:
        wecom_region: (left, top, width, height) 窗口位置
        ratio: 裁剪比例 {x, y, width, height} (0-1)

    Returns:
        消息区域截图
    """
    left = wecom_region[0] + int(wecom_region[2] * ratio["x"])
    top = wecom_region[1] + int(wecom_region[3] * ratio["y"])
    w = int(wecom_region[2] * ratio["width"])
    h = int(wecom_region[3] * ratio["height"])

    return capture_screen((left, top, w, h))


def get_screen_size() -> Tuple[int, int]:
    """获取主屏幕分辨率

    Returns:
        (width, height)
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        return (monitor["width"], monitor["height"])
