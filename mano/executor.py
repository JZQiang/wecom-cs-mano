"""键鼠控制 — 基于 pynput（复用 mano-skill 方案）"""

import time
import subprocess
import platform
import os
from typing import Optional, Tuple

from pynput import mouse, keyboard
from pynput.keyboard import Key
from pynput.mouse import Button


class ActionExecutor:
    """桌面 GUI 操作执行器"""

    def __init__(self):
        self.mouse_ctrl = mouse.Controller()
        self.keyboard_ctrl = keyboard.Controller()

    # ==================== 鼠标操作 ====================

    def move_to(self, x: int, y: int, duration: float = 0.2):
        """平滑移动鼠标到指定坐标

        Args:
            x, y: 目标屏幕坐标
            duration: 动画持续时间（秒）
        """
        current = self.mouse_ctrl.position
        steps = max(5, int(duration * 30))

        for i in range(steps + 1):
            t = i / steps
            new_x = current[0] + (x - current[0]) * t
            new_y = current[1] + (y - current[1]) * t
            self.mouse_ctrl.position = (new_x, new_y)
            time.sleep(duration / steps)

    def click(self, x: Optional[int] = None, y: Optional[int] = None,
              button: str = "left", count: int = 1):
        """点击指定位置

        Args:
            x, y: 屏幕坐标（None=当前位置）
            button: "left" / "right" / "middle"
            count: 点击次数
        """
        if x is not None and y is not None:
            self.mouse_ctrl.position = (x, y)
            time.sleep(0.1)

        btn = getattr(Button, button)
        self.mouse_ctrl.click(btn, count)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """双击"""
        self.click(x, y, count=2)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """右键单击"""
        self.click(x, y, button="right")

    # ==================== 键盘操作 ====================

    def type_text(self, text: str):
        """输入文本（通过剪贴板粘贴，避免输入法冲突）

        Args:
            text: 要输入的文本
        """
        system = platform.system()
        # 写入剪贴板
        if system == "Darwin":
            proc = subprocess.run(["pbcopy"], input=text.encode("utf-8"),
                                  capture_output=True, timeout=3)
        elif system == "Windows":
            proc = subprocess.run(["clip"], input=text.encode("utf-16le"),
                                  capture_output=True, timeout=3)
        else:
            proc = subprocess.run(["xclip", "-selection", "clipboard"],
                                  input=text.encode("utf-8"),
                                  capture_output=True, timeout=3)

        # 粘贴（Cmd+V / Ctrl+V）
        paste_key = Key.cmd if system == "Darwin" else Key.ctrl
        self.keyboard_ctrl.press(paste_key)
        self.keyboard_ctrl.press("v")
        self.keyboard_ctrl.release("v")
        self.keyboard_ctrl.release(paste_key)
        time.sleep(0.2)

    def press_key(self, key: str):
        """按单个键

        Args:
            key: 键名（'enter', 'tab', 'escape' 等）
        """
        key_map = {
            "enter": Key.enter,
            "tab": Key.tab,
            "escape": Key.esc,
            "backspace": Key.backspace,
            "delete": Key.delete,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "space": Key.space,
            "cmd": Key.cmd,
            "ctrl": Key.ctrl,
            "shift": Key.shift,
            "alt": Key.alt,
        }
        k = key_map.get(key.lower(), key)
        self.keyboard_ctrl.press(k)
        self.keyboard_ctrl.release(k)

    def hotkey(self, *keys: str):
        """组合键

        Args:
            *keys: 键名列表，如 ("cmd", "c") 表示 Cmd+C
        """
        key_map = {
            "cmd": Key.cmd, "command": Key.cmd,
            "ctrl": Key.ctrl, "control": Key.ctrl,
            "shift": Key.shift,
            "alt": Key.alt, "option": Key.alt,
            "enter": Key.enter, "return": Key.enter,
            "tab": Key.tab, "escape": Key.esc,
        }

        pressed = []
        try:
            for k in keys:
                obj = key_map.get(k.lower(), k)
                self.keyboard_ctrl.press(obj)
                pressed.append(obj)
                time.sleep(0.02)

            time.sleep(0.05)

            for obj in reversed(pressed):
                self.keyboard_ctrl.release(obj)
                time.sleep(0.02)
        except Exception as e:
            # 确保释放所有按键
            for obj in pressed:
                try:
                    self.keyboard_ctrl.release(obj)
                except Exception:
                    pass
            raise e

    def scroll(self, clicks: int, x: Optional[int] = None,
               y: Optional[int] = None):
        """滚动

        Args:
            clicks: 滚动量（正=上，负=下）
            x, y: 滚动位置
        """
        if x is not None and y is not None:
            self.mouse_ctrl.position = (x, y)
            time.sleep(0.1)

        self.mouse_ctrl.scroll(0, clicks)

    # ==================== 应用操作 ====================

    def open_app(self, app_name: str):
        """打开应用（macOS）

        Args:
            app_name: 应用名称或路径
        """
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
            time.sleep(1.5)
        else:
            raise NotImplementedError(f"暂不支持 {system} 系统")

    def move_window_to_primary(self, app_name: str):
        """将应用窗口移动到主屏幕（macOS）

        Args:
            app_name: 应用进程名
        """
        try:
            script = (
                f'tell application "System Events"\n'
                f'    tell process "{app_name}"\n'
                f'        set position of window 1 to {{0, 25}}\n'
                f'    end tell\n'
                f'end tell'
            )
            subprocess.run(["osascript", "-e", script],
                           timeout=3, capture_output=True)
        except Exception:
            pass  # 尽力而为
