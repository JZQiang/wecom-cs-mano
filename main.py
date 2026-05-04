#!/usr/bin/env python3
"""
企业微信智能客服 — 全自动版 V4
全流程自包含：红点检测 → 点击进群 → 截图会话 → OCR提取文字 → AI回复 → 打字发送

不需要外部 cron job 配合，独立运行。
"""

import json
import os
import sys
import time
import signal
import logging
import traceback
import hashlib
import subprocess
import platform
import re
import requests
from datetime import datetime
from typing import Optional, Tuple, List
from PIL import Image, ImageChops
from mano.executor import ActionExecutor

# ─── 常量 ────────────────────────────────────────────
PID_FILE = "logs/pid.txt"

# 企业微信三列布局（基于窗口比例）
# 第一列（功能列表）约占窗口6-7%宽，第二列从7%开始确保不包含第一列
COL2_RATIO = {"x": 0.15, "y": 0.00, "width": 0.237, "height": 1.00}   # 群聊列表 (15%~38.7%)
COL3_RATIO = {"x": 0.387, "y": 0.00, "width": 0.613, "height": 1.00}   # 会话窗口 (38.7%~100%)

# 红点检测参数
RED_R_MIN = 180
RED_GB_MAX = 120
RED_MIN_PIXELS = 3


class WeComAssistant:
    """企业微信智能助理 — 全自动版"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.running = True
        self.executor = ActionExecutor()
        self.ocr = None  # lazy init

        # 窗口
        self.wecom_region: Optional[Tuple[int, int, int, int]] = None
        self.check_interval = self.config.get("check_interval_seconds", 3)

        # 去重
        self._processed_hashes = set()

        # AI 配置
        ai_cfg = self.config.get("ai", {})
        self.ai_provider = ai_cfg.get("provider", "deepseek")
        self.ai_model = ai_cfg.get("model", "deepseek-chat")
        self.ai_base_url = ai_cfg.get("base_url", "https://api.deepseek.com").rstrip("/v1")
        self.ai_key = ai_cfg.get("api_key", "")
        self.system_prompt = ai_cfg.get("system_prompt",
            "你是企业微信智能客服「快亮家装饰」的AI助手。语气友好专业，简洁高效。回复不超过100字。如果不知道答案，引导联系人工客服。")

        # 日志
        os.makedirs("logs", exist_ok=True)
        log_file = self.config.get("logging", {}).get("log_file", "logs/monitor.log")
        logging.basicConfig(
            filename=log_file, level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        self.log = logging.getLogger(__name__)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _load_config(self, config_path: Optional[str]) -> dict:
        if not config_path:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, "config.json")

        default = {
            "check_interval_seconds": 3,
            "wecom_process_name": "企业微信",
            "logging": {"log_file": "logs/monitor.log"},
            "ai": {}
        }

        if os.path.exists(config_path):
            with open(config_path) as f:
                loaded = json.load(f)
                default.update(loaded)

        # 如果 AI key 没配置，从 .env 或 Hermes config 读取
        ai = default.get("ai", {})
        if not ai.get("api_key"):
            # 优先从 .env 文件读取
            env_file = os.path.expanduser("~/.hermes/.env")
            if os.path.exists(env_file):
                try:
                    with open(env_file) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("DEEPSEEK_API_KEY"):
                                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                if key:
                                    ai["api_key"] = key
                                    break
                except Exception:
                    pass

        if not ai.get("api_key"):
            try:
                hermes_config = os.path.expanduser("~/.hermes/config.yaml")
                if os.path.exists(hermes_config):
                    with open(hermes_config) as f:
                        for line in f:
                            if line.strip().startswith("api_key:"):
                                key = line.split(":", 1)[1].strip().strip('"').strip("'")
                                if key:
                                    ai["api_key"] = key
                                    break
            except Exception:
                pass

        # 尝试环境变量
        if not ai.get("api_key"):
            for env in ["DEEPSEEK_API_KEY", "BAILIAN_API_KEY", "OPENROUTER_API_KEY"]:
                val = os.environ.get(env)
                if val:
                    ai["api_key"] = val
                    break

        default["ai"] = ai
        return default

    def _signal_handler(self, signum, frame):
        print(f"\n🛑 收到信号 {signum}，正在停止...")
        self.running = False

    def _log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{level}] {msg}")
        getattr(self.log, level.lower(), self.log.info)(msg)

    # ─── 窗口管理 ──────────────────────────────────

    def _detect_window(self) -> bool:
        if platform.system() != "Darwin":
            return False
        try:
            script = (
                f'tell application "System Events" to tell process '
                f'"{self.config["wecom_process_name"]}" to if exists window 1 '
                f'then get {{position of window 1, size of window 1}}'
            )
            r = subprocess.run(["osascript", "-e", script],
                               capture_output=True, text=True, timeout=5)
            if r.returncode != 0 or not r.stdout.strip():
                return False
            # Parse AppleScript list output: {{697, 38}, {1060, 640}}
            nums = re.findall(r'\d+', r.stdout)
            if len(nums) >= 4:
                self.wecom_region = (int(nums[0]), int(nums[1]),
                                     int(nums[2]), int(nums[3]))
                return True
        except Exception:
            pass
        return False

    def _get_region(self, ratio: dict) -> Optional[Tuple[int, int, int, int]]:
        if not self.wecom_region:
            return None
        l, t, w, h = self.wecom_region
        return (l + int(w * ratio["x"]), t + int(h * ratio["y"]),
                int(w * ratio["width"]), int(h * ratio["height"]))

    def _focus_wecom(self):
        try:
            subprocess.run(["osascript", "-e",
                f'tell application "{self.config["wecom_process_name"]}" to activate'],
                timeout=5, capture_output=True)
            time.sleep(0.5)
        except Exception:
            pass

    # ─── 截图 ──────────────────────────────────────

    def _screenshot(self, region: Tuple[int, int, int, int]) -> Image.Image:
        from mano.capture import capture_screen
        return capture_screen(region)

    # ─── 红点检测 ──────────────────────────────────

    def _find_red_dots(self, img: Image.Image) -> List[Tuple[int, int]]:
        """检测图片中的红色圆点"""
        pixels = img.load()
        w, h = img.size
        dots = []
        for y in range(h):
            x = 0
            while x < w:
                r, g, b = pixels[x, y][:3]
                if r > RED_R_MIN and g < RED_GB_MAX and b < RED_GB_MAX:
                    start_x = x
                    while x < w:
                        r2, g2, b2 = pixels[x, y][:3]
                        if r2 > RED_R_MIN and g2 < RED_GB_MAX and b2 < RED_GB_MAX:
                            x += 1
                        else:
                            break
                    if x - start_x >= RED_MIN_PIXELS:
                        dots.append((start_x + (x - start_x) // 2, y))
                x += 1
        return dots

    def _cluster_dots(self, dots: List[Tuple[int, int]],
                       min_per_cluster: int = 3) -> List[Tuple[int, int]]:
        if not dots:
            return []
        dots.sort(key=lambda d: d[1])
        clusters = []
        cur = [dots[0]]
        for i in range(1, len(dots)):
            if abs(dots[i][1] - cur[-1][1]) < 5:
                cur.append(dots[i])
            else:
                if len(cur) >= min_per_cluster:
                    avg_x = sum(d[0] for d in cur) // len(cur)
                    avg_y = sum(d[1] for d in cur) // len(cur)
                    clusters.append((avg_x, avg_y))
                cur = [dots[i]]
        if len(cur) >= min_per_cluster:
            avg_x = sum(d[0] for d in cur) // len(cur)
            avg_y = sum(d[1] for d in cur) // len(cur)
            clusters.append((avg_x, avg_y))
        return clusters

    def _find_column_boundary(self, img: Image.Image) -> int:
        """检测截图中的第一列和第二列之间的分割线位置
        
        通过从左侧向右扫描像素颜色变化，找到第一个明显的颜色突变。
        企业微信第一列和第二列之间的分割线通常在截图左端附近。
        
        Returns:
            分割线的x坐标（相对于截图的像素位置），0表示未找到
        """
        try:
            import numpy as np
            arr = np.array(img.convert('RGB'))
            h, w = arr.shape[:2]
            if w < 20 or h < 20:
                return 0
            
            # 取中间区域（20%-80%高度），避开顶部标题和底部
            y_start = int(h * 0.2)
            y_end = int(h * 0.8)
            if y_end <= y_start:
                return 0
            region = arr[y_start:y_end, :, :]
            
            # 计算每一列的平均颜色
            col_means = np.mean(region, axis=0).astype(float)  # (w, 3)
            
            # 计算相邻列之间的颜色差异
            diffs = np.sqrt(np.sum((col_means[1:] - col_means[:-1])**2, axis=1))
            
            # 找第一个超过阈值的颜色突变（从最左边开始）
            # 阈值：颜色差异大于30通常就是分割线
            threshold = 30.0
            # 限制搜索范围：分割线通常在截图左侧30px以内
            search_limit = min(40, len(diffs))
            
            for i in range(search_limit):
                if diffs[i] > threshold:
                    self._log("DEBUG", f"📏 检测到分割线: cx={i+1}px, 差异值={diffs[i]:.1f}")
                    return i + 1
            
            # 如果没找到，用更低的阈值再试一次
            threshold2 = 15.0
            for i in range(search_limit):
                if diffs[i] > threshold2:
                    self._log("DEBUG", f"📏 分割线(低阈值): cx={i+1}px, 差异值={diffs[i]:.1f}")
                    return i + 1
            
            self._log("DEBUG", "📏 未检测到明显分割线")
            return 0
        except Exception as e:
            self._log("WARN", f"⚠️ 分割线检测异常: {e}")
            return 0

    def _screen_red_dots(self, col2_img: Image.Image,
                          col2_region: Tuple[int, int, int, int]) -> List[Tuple[int, int]]:
        """获取红点在屏幕上的坐标"""
        dots = self._find_red_dots(col2_img)
        clusters = self._cluster_dots(dots)
        return [(col2_region[0] + cx, col2_region[1] + cy) for cx, cy in clusters]

    # ─── 点击操作 ──────────────────────────────────

    def _click_at(self, x: int, y: int):
        self.executor.move_to(x, y, 0.3)
        time.sleep(0.15)
        self.executor.click(x, y)
        time.sleep(0.8)

    def _click_external_chat_list(self):
        """点击第一列中的「外部群聊」按钮
        用 OCR 定位文字位置，精确点击
        """
        if not self.wecom_region:
            return
        if not self._init_ocr():
            return

        l, t, w, h = self.wecom_region
        # 截第一列
        col1 = (l, t, int(w * 0.07), h)
        from mano.capture import capture_screen
        col1_img = capture_screen(col1)

        import numpy as np
        img_np = np.array(col1_img)
        results = self.ocr.readtext(img_np)

        target = None
        for box, text, conf in results:
            if any(kw in text for kw in ["外部群聊", "外部聊天", "外部"]):
                # box = [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                cx = (box[0][0] + box[2][0]) // 2
                cy = (box[0][1] + box[2][1]) // 2
                target = (col1[0] + cx, col1[1] + cy)
                self._log("INFO", f"🔍 OCR找到「{text}」@ ({target[0]}, {target[1]}) conf={conf:.2f}")
                break

        if not target:
            self._log("WARN", "⚠️ OCR未找到「外部群聊」，使用默认位置")
            target = (l + int(w * 0.067), t + int(h * 0.80))

        self.executor.move_to(target[0], target[1], 0.3)
        time.sleep(0.1)
        self.executor.click(target[0], target[1])
        time.sleep(0.5)
        self._log("INFO", f"👆 点击「外部群聊」 ({target[0]}, {target[1]})")

    def _click_chat_row(self, red_dot_screen: Tuple[int, int],
                         col2_region: Tuple[int, int, int, int]):
        """点击红点所在群聊行
        红点通常在群聊条目的右侧，往左偏移点中条目中间
        确保点击在第二列范围内，绝不误触第一列
        """
        dot_x, dot_y = red_dot_screen
        # 第二列中间偏左位置（确保不在第一列）
        col2_center_x = col2_region[0] + col2_region[2] // 2
        # 第二列安全左边界 = 基于窗口比例计算（与红点过滤一致，~12%窗口宽度）
        if self.wecom_region:
            safe_left = self.wecom_region[0] + int(self.wecom_region[2] * 0.12) + 10
        else:
            safe_left = col2_region[0] + 100
        # 红点往左偏移点标题，但绝不能小于安全左边界
        click_x = max(safe_left, min(dot_x - 40, col2_center_x))
        self.executor.move_to(click_x, dot_y, 0.3)
        time.sleep(0.15)
        self.executor.click(click_x, dot_y)
        time.sleep(1.2)
        self._log("INFO", f"👆 点击群聊 (x={click_x}, y={dot_y}), safe_left={safe_left}")

    # ─── OCR（EasyOCR 本地文字提取） ───────────────

    def _init_ocr(self):
        if self.ocr is not None:
            return True
        try:
            import easyocr
            self.ocr = easyocr.Reader(
                ['ch_sim', 'en'], gpu=False,
                model_storage_directory=os.path.expanduser('~/.EasyOCR/model'),
                download_enabled=False
            )
            self._log("INFO", "✅ EasyOCR 加载完成")
            return True
        except Exception as e:
            self._log("WARN", f"⚠️ EasyOCR 加载失败: {e}")
            return False

    def _ocr_image(self, img: Image.Image) -> str:
        """提取图片文字"""
        if not self._init_ocr():
            return ""
        try:
            # EasyOCR 需要 numpy array
            import numpy as np
            img_np = np.array(img)
            results = self.ocr.readtext(img_np)
            texts = [text.strip() for _, text, conf in results if conf > 0.3]
            return "\n".join(texts)
        except Exception as e:
            self._log("WARN", f"⚠️ OCR 识别失败: {e}")
            return ""

    # ─── AI 回复 ───────────────────────────────────

    def _generate_reply(self, ocr_text: str) -> Optional[str]:
        """调用 AI 生成回复（带知识库检索）"""
        if not self.ai_key:
            self._log("WARN", "⚠️ 未配置 API Key，无法生成回复")
            return None

        try:
            # 检索知识库
            kb_context = ""
            try:
                if not hasattr(self, '_kb') or not self._kb:
                    from scripts.kb_client import KnowledgeBase
                    self._kb = KnowledgeBase()
                    self._kb.init()
                if self._kb.is_ready():
                    kb_context = self._kb.format_context(ocr_text)
                    self._log("INFO", f"📚 知识库检索到相关片段")
            except Exception:
                pass

            # 组装 system prompt + 知识库内容
            system_content = self.system_prompt
            if kb_context:
                system_content += kb_context

            resp = requests.post(
                f"{self.ai_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.ai_key}",
                         "Content-Type": "application/json"},
                json={
                    "model": self.ai_model,
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content":
                            f"以下是企业微信群聊的截图OCR识别结果。请找出带有「(@微信)」标识的客户消息，并以快亮家装饰客服的身份回复。\n\n{ocr_text}\n\n注意：只回复(@微信)客户，不超过100字。"}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 200,
                },
                timeout=20
            )

            if resp.status_code == 200:
                reply = resp.json()["choices"][0]["message"]["content"].strip()
                return reply
            else:
                self._log("WARN", f"⚠️ AI API 失败: {resp.status_code} {resp.text[:200]}")
                return None

        except Exception as e:
            self._log("WARN", f"⚠️ AI 回复异常: {e}")
            return None

    # ─── 哈希（去重） ──────────────────────────────

    def _image_hash(self, img: Image.Image) -> str:
        small = img.resize((16, 16)).tobytes()
        return hashlib.md5(small).hexdigest()

    # ─── 主循环 ────────────────────────────────────

    def run(self):
        self._log("INFO", "=" * 55)
        self._log("INFO", "🚀 企业微信智能助理 V4 启动")
        self._log("INFO", f"   检查间隔: {self.check_interval}s")
        self._log("INFO", f"   AI 模型: {self.ai_model}")
        self._log("INFO", f"   OCR: EasyOCR (本地)")
        self._log("INFO", "   全自动: 红点→点击→OCR→AI回复→打字")
        self._log("INFO", "=" * 55)

        cycle_count = 0
        no_window_count = 0

        while self.running:
            try:
                cycle_count += 1

                # ═══ 1. 检测窗口 ═══
                if self.wecom_region is None or cycle_count % 200 == 0:
                    if not self._detect_window():
                        no_window_count += 1
                        if no_window_count % 10 == 0:
                            self._log("WARN", f"⏳ 等待企业微信窗口... (已等{no_window_count * self.check_interval}s)")
                        time.sleep(self.check_interval)
                        continue
                    else:
                        no_window_count = 0

                # ═══ 2. 截图第二列（群聊列表） ═══
                col2 = self._get_region(COL2_RATIO)
                if not col2:
                    time.sleep(self.check_interval)
                    continue

                col2_img = self._screenshot(col2)

                # ═══ 3. 红点检测 ═══
                red_dots = self._screen_red_dots(col2_img, col2)

                if not red_dots:
                    time.sleep(self.check_interval)
                    continue

                # 去重
                h = self._image_hash(col2_img)
                if h in self._processed_hashes:
                    time.sleep(self.check_interval)
                    continue
                self._processed_hashes.add(h)
                if len(self._processed_hashes) > 50:
                    self._processed_hashes.clear()

                self._log("INFO", f"🔴 检测到 {len(red_dots)} 个红点！")

                # ═══ 4. 点击进入群聊 ═══
                # 取最右侧的红点（避开第一列区域）
                self._focus_wecom()
                first_dot = max(red_dots, key=lambda d: d[0])
                self._log("INFO", f"🎯 选取最右侧红点: ({first_dot[0]}, {first_dot[1]})")
                self._click_chat_row(first_dot, col2)

                # ═══ 5. 截图第三列（会话窗口） ═══
                col3 = self._get_region(COL3_RATIO)
                if not col3:
                    time.sleep(self.check_interval)
                    continue

                time.sleep(1.5)
                session_img = self._screenshot(col3)
                self._log("INFO", f"📸 会话截图: {session_img.size}")

                # ═══ 7. OCR 提取文字 ═══
                ocr_text = self._ocr_image(session_img)
                if not ocr_text:
                    self._log("WARN", "⚠️ OCR 未提取到文字，跳过")
                    time.sleep(2)
                    continue

                self._log("INFO", f"📝 OCR 内容 ({len(ocr_text)}字符):")
                for line in ocr_text.split("\n")[:5]:
                    if line.strip():
                        self._log("INFO", f"   {line.strip()[:80]}")

                # ═══ 8. AI 生成回复 ═══
                reply = self._generate_reply(ocr_text)

                if not reply:
                    self._log("WARN", "⚠️ 回复生成失败，跳过")
                    time.sleep(2)
                    continue

                self._log("INFO", f"💬 AI 回复: {reply[:80]}...")

                # ═══ 8. 打字发送 ═══
                l, t, w, h = self.wecom_region
                # 先点第三列中间区域激活会话窗口
                col3_mid_x = l + int(w * 0.50)
                col3_mid_y = t + int(h * 0.40)
                self.executor.move_to(col3_mid_x, col3_mid_y, 0.2)
                time.sleep(0.1)
                self.executor.click(col3_mid_x, col3_mid_y)
                time.sleep(0.3)

                # 再点输入框（第三列底部偏左）
                input_x = l + int(w * 0.40)
                input_y = t + int(h * 0.90)
                self.executor.move_to(input_x, input_y, 0.3)
                time.sleep(0.15)
                self.executor.click(input_x, input_y)
                time.sleep(0.3)

                # 粘贴 + 回车
                self.executor.type_text(reply)
                time.sleep(0.3)
                self.executor.press_key("enter")
                time.sleep(0.5)
                self._log("INFO", "✅ 回复已发送 ✓")

                # ═══ 10. 冷却 ═══
                time.sleep(1)

            except KeyboardInterrupt:
                self._log("INFO", "🛑 用户中断")
                self.running = False
                break
            except Exception as e:
                self._log("ERROR", f"❌ 异常: {e}")
                self._log("ERROR", traceback.format_exc())
                time.sleep(self.check_interval * 2)

        self._log("INFO", "👋 智能助理已停止")

    def stop(self):
        self.running = False


def main():
    config_path = os.environ.get("WECOM_CONFIG_PATH")
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    assistant = WeComAssistant(config_path)
    assistant.run()


if __name__ == "__main__":
    main()
