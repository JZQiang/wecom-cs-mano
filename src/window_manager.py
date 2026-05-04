"""窗口管理器 — 定位和跟踪企业微信窗口位置"""

import time
import subprocess
import platform
from typing import Optional, Tuple

from mano.capture import capture_screen


class WindowManager:
    """企业微信窗口管理器"""

    def __init__(self, config: dict):
        self.config = config
        self.process_name = config.get("wecom_process_name", "WeCom")
        self.window_title = config.get("wecom_window_title", "企业微信")
        self.auto_detect_interval = config.get("window", {}).get(
            "auto_detect_interval", 300)
        self.ocr_region_ratio = config.get("window", {}).get(
            "ocr_region_ratio", {"x": 0.05, "y": 0.1,
                                 "width": 0.9, "height": 0.7})

        self._cached_region: Optional[Tuple[int, int, int, int]] = None
        self._last_detect_time = 0
        self._message_area: Optional[Tuple[int, int, int, int]] = None

    def detect_wecom_window(self) -> Optional[Tuple[int, int, int, int]]:
        """检测企业微信窗口位置（macOS）

        Returns:
            (left, top, width, height) 或 None（未找到）
        """
        system = platform.system()
        if system != "Darwin":
            raise NotImplementedError(f"暂不支持 {system} 系统")

        try:
            # 使用 AppleScript 获取窗口位置
            script = f'''
            tell application "System Events"
                tell process "{self.process_name}"
                    if exists window 1 then
                        set winPos to position of window 1
                        set winSize to size of window 1
                        return (item 1 of winPos) & "," & (item 2 of winPos) & "," & (item 1 of winSize) & "," & (item 2 of winSize)
                    end if
                end tell
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0 or not result.stdout.strip():
                print("⚠️ 未找到企业微信窗口")
                return None

            parts = result.stdout.strip().split(",")
            if len(parts) == 4:
                left, top, width, height = map(int, parts)
                if width > 0 and height > 0:
                    self._cached_region = (left, top, width, height)
                    self._update_message_area()
                    return self._cached_region

            return None

        except subprocess.TimeoutExpired:
            print("⚠️ 检测窗口超时")
            return None
        except Exception as e:
            print(f"⚠️ 窗口检测失败: {e}")
            return None

    def _update_message_area(self):
        """计算消息区域坐标"""
        if not self._cached_region:
            return

        left, top, width, height = self._cached_region
        ratio = self.ocr_region_ratio

        msg_left = left + int(width * ratio["x"])
        msg_top = top + int(height * ratio["y"])
        msg_w = int(width * ratio["width"])
        msg_h = int(height * ratio["height"])

        self._message_area = (msg_left, msg_top, msg_w, msg_h)

    def get_wecom_region(self, force: bool = False) -> Optional[Tuple[int, int, int, int]]:
        """获取企业微信窗口区域（带缓存）

        Args:
            force: 是否强制重新检测

        Returns:
            (left, top, width, height)
        """
        now = time.time()
        if (force or self._cached_region is None or
                now - self._last_detect_time > self.auto_detect_interval):
            self._last_detect_time = now
            return self.detect_wecom_window()

        return self._cached_region

    def get_message_area(self) -> Optional[Tuple[int, int, int, int]]:
        """获取消息区域坐标"""
        if self._message_area is None:
            self.get_wecom_region(force=True)
        return self._message_area

    def is_wecom_running(self) -> bool:
        """检查企业微信是否在运行"""
        try:
            result = subprocess.run(
                ["pgrep", "-x", self.process_name],
                capture_output=True, timeout=3
            )
            return result.returncode == 0
        except Exception:
            return False

    def focus_wecom(self):
        """将企业微信窗口置于前台"""
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "{self.process_name}" to activate'],
                timeout=5, capture_output=True
            )
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ 切换窗口失败: {e}")
