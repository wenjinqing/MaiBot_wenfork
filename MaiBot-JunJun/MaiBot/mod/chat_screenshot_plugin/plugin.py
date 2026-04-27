"""
聊天记录截图插件

用于截取聊天记录并生成截图，主要用于举证场景
支持群聊→私聊、私聊→群聊的转发

Version: 1.0.0
Author: Assistant
"""

from typing import List, Tuple, Type, Optional, Dict, Any
import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

from src.common.logger import get_logger
from src.plugin_system.base.base_plugin import BasePlugin
from src.plugin_system.apis.plugin_register_api import register_plugin
from src.plugin_system.base.base_action import BaseAction, ActionActivationType
from src.plugin_system.base.base_command import BaseCommand
from src.plugin_system.base.component_types import ComponentInfo, ChatMode
from src.plugin_system.base.config_types import ConfigField
from src.common.database.database_model import Messages, db
from src.common.cross_chat_sender import CrossChatSender

logger = get_logger("chat_screenshot_plugin")


class ChatScreenshotGenerator:
    """聊天记录截图生成器"""

    def __init__(self, config: dict):
        self.config = config
        self.width = config.get("screenshot_width", 800)
        self.font_size = config.get("font_size", 16)
        self.bg_color = config.get("background_color", "#F5F5F5")
        self.user_bubble_color = config.get("user_bubble_color", "#95EC69")
        self.bot_bubble_color = config.get("bot_bubble_color", "#FFFFFF")
        self.other_bubble_color = config.get("other_bubble_color", "#FFFFFF")
        self.text_color = config.get("text_color", "#000000")
        self.timestamp_color = config.get("timestamp_color", "#999999")
        self.bubble_radius = config.get("bubble_radius", 8)
        self.message_spacing = config.get("message_spacing", 10)
        self.show_timestamp = config.get("show_timestamp", True)

        # 尝试加载字体
        try:
            # Windows 系统字体
            self.font = ImageFont.truetype("msyh.ttc", self.font_size)
            self.small_font = ImageFont.truetype("msyh.ttc", self.font_size - 4)
        except:
            try:
                # 备用字体
                self.font = ImageFont.truetype("arial.ttf", self.font_size)
                self.small_font = ImageFont.truetype("arial.ttf", self.font_size - 4)
            except:
                # 使用默认字体
                self.font = ImageFont.load_default()
                self.small_font = ImageFont.load_default()

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """将十六进制颜色转换为RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _draw_rounded_rectangle(self, draw: ImageDraw, xy: tuple, fill: str, radius: int):
        """绘制圆角矩形"""
        x1, y1, x2, y2 = xy
        fill_rgb = self._hex_to_rgb(fill)

        # 绘制主体矩形
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill_rgb)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill_rgb)

        # 绘制四个圆角
        draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill_rgb)
        draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill_rgb)
        draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill_rgb)
        draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill_rgb)

    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """文本换行"""
        lines = []
        current_line = ""

        for char in text:
            test_line = current_line + char
            bbox = self.font.getbbox(test_line)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    def generate_screenshot(self, messages: List[Dict], target_user_id: str = None) -> bytes:
        """
        生成聊天记录截图

        Args:
            messages: 消息列表
            target_user_id: 目标用户ID（用于高亮显示）

        Returns:
            PNG图片的字节数据
        """
        if not messages:
            # 创建空白图片
            img = Image.new('RGB', (self.width, 100), self._hex_to_rgb(self.bg_color))
            draw = ImageDraw.Draw(img)
            draw.text((self.width // 2, 50), "暂无聊天记录",
                     fill=self._hex_to_rgb(self.text_color),
                     font=self.font, anchor="mm")

            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()

        # 计算所需高度
        padding = 20
        y_offset = padding
        message_heights = []

        for msg in messages:
            text = msg.get('text', '')
            nickname = msg.get('nickname', '未知用户')
            timestamp = msg.get('timestamp', '')
            is_bot = msg.get('is_bot', False)

            # 计算消息高度
            max_bubble_width = int(self.width * 0.6)
            lines = self._wrap_text(text, max_bubble_width - 20)

            msg_height = padding
            if self.show_timestamp:
                msg_height += 20  # 时间戳高度
            msg_height += 20  # 昵称高度
            msg_height += len(lines) * (self.font_size + 5) + 20  # 文本高度 + 内边距

            message_heights.append(msg_height)
            y_offset += msg_height + self.message_spacing

        # 创建图片
        total_height = y_offset + padding
        img = Image.new('RGB', (self.width, total_height), self._hex_to_rgb(self.bg_color))
        draw = ImageDraw.Draw(img)

        # 绘制消息
        y_offset = padding
        for i, msg in enumerate(messages):
            text = msg.get('text', '')
            nickname = msg.get('nickname', '未知用户')
            timestamp = msg.get('timestamp', '')
            is_bot = msg.get('is_bot', False)
            user_id = msg.get('user_id', '')

            # 判断消息方向
            is_right = (user_id == target_user_id) if target_user_id else False

            # 选择气泡颜色
            if is_bot:
                bubble_color = self.bot_bubble_color
            elif is_right:
                bubble_color = self.user_bubble_color
            else:
                bubble_color = self.other_bubble_color

            # 绘制时间戳（居中）
            if self.show_timestamp and timestamp:
                ts_bbox = self.small_font.getbbox(timestamp)
                ts_width = ts_bbox[2] - ts_bbox[0]
                draw.text((self.width // 2 - ts_width // 2, y_offset),
                         timestamp,
                         fill=self._hex_to_rgb(self.timestamp_color),
                         font=self.small_font)
                y_offset += 25

            # 绘制昵称
            nick_bbox = self.small_font.getbbox(nickname)
            nick_width = nick_bbox[2] - nick_bbox[0]

            if is_right:
                nick_x = self.width - padding - nick_width
            else:
                nick_x = padding

            draw.text((nick_x, y_offset), nickname,
                     fill=self._hex_to_rgb(self.text_color),
                     font=self.small_font)
            y_offset += 25

            # 计算气泡大小
            max_bubble_width = int(self.width * 0.6)
            lines = self._wrap_text(text, max_bubble_width - 20)

            # 计算实际气泡宽度
            max_line_width = 0
            for line in lines:
                bbox = self.font.getbbox(line)
                line_width = bbox[2] - bbox[0]
                max_line_width = max(max_line_width, line_width)

            bubble_width = min(max_line_width + 20, max_bubble_width)
            bubble_height = len(lines) * (self.font_size + 5) + 20

            # 绘制气泡
            if is_right:
                bubble_x1 = self.width - padding - bubble_width
                bubble_x2 = self.width - padding
            else:
                bubble_x1 = padding
                bubble_x2 = padding + bubble_width

            bubble_y1 = y_offset
            bubble_y2 = y_offset + bubble_height

            self._draw_rounded_rectangle(
                draw,
                (bubble_x1, bubble_y1, bubble_x2, bubble_y2),
                bubble_color,
                self.bubble_radius
            )

            # 绘制文本
            text_y = y_offset + 10
            for line in lines:
                draw.text((bubble_x1 + 10, text_y), line,
                         fill=self._hex_to_rgb(self.text_color),
                         font=self.font)
                text_y += self.font_size + 5

            y_offset += bubble_height + self.message_spacing

        # 保存为字节流
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()


class ChatScreenshotAction(BaseAction):
    """聊天记录截图Action - 供大模型调用"""

    action_name = "chat_screenshot_action"
    action_description = "截取特定用户的聊天记录并生成截图，用于举证或回顾历史对话"
    activation_type = ActionActivationType.LLM_JUDGE
    mode_enable = ChatMode.ALL
    parallel_action = False

    activation_keywords = ["截图", "聊天记录", "举证", "证据", "历史消息", "说过", "screenshot", "chat history"]
    keyword_case_sensitive = False

    action_parameters = {
        "user_id": "目标用户ID（必填）。要截取哪个用户的聊天记录",
        "platform": "平台（必填）。如：qq、wechat等",
        "message_count": "截取消息数量（可选）。默认20条，最多100条",
        "chat_type": "聊天类型（可选）。group=群聊，private=私聊，all=全部。默认为all",
        "send_to": "发送目标（可选）。private=发送到私聊，group=发送到群聊，current=发送到当前会话。默认为current"
    }

    action_require = [
        "【适合使用的场景】",
        "1. 用户否认说过某些话，需要举证",
        "2. 用户要求查看历史聊天记录",
        "3. 需要回顾之前的对话内容",
        "4. 用户要求'截图'、'翻聊天记录'等",
        "",
        "【参数说明】",
        "1. user_id和platform是必填参数，从当前消息中获取",
        "2. message_count默认20条，可根据需要调整（最多100条）",
        "3. chat_type用于筛选聊天类型：",
        "   - group: 只截取群聊记录",
        "   - private: 只截取私聊记录",
        "   - all: 截取所有记录（默认）",
        "4. send_to用于指定发送目标：",
        "   - current: 发送到当前会话（默认）",
        "   - private: 如果当前在群聊，会额外私发给用户",
        "   - group: 如果当前在私聊，会额外发送到群聊",
        "",
        "【使用示例】",
        "1. 用户在群里说'我没说过这话'，可以截取该用户的群聊记录发到群里举证",
        "2. 用户在私聊说'你在群里说了什么'，可以截取群聊记录发到私聊",
        "3. 用户要求'看看我之前说了什么'，截取历史记录发到当前会话",
        "",
        "【注意事项】",
        "1. 只截取该用户发送的消息，不包括其他人的消息",
        "2. 截图会显示消息时间、昵称和内容",
        "3. 转发到其他会话时需要确保该用户在目标会话中有聊天记录",
        "4. 不要滥用此功能，仅在必要时使用",
        "5. 私聊内容不应该在群里公开，注意隐私保护"
    ]

    associated_types = ["text", "command"]

    async def execute(self) -> Tuple[bool, str]:
        """执行截图操作"""
        try:
            # 获取参数
            user_id = self.action_data.get("user_id", "").strip()
            platform = self.action_data.get("platform", "").strip()
            message_count = int(self.action_data.get("message_count", 20))
            chat_type = self.action_data.get("chat_type", "all").strip().lower()
            send_to = self.action_data.get("send_to", "current").strip().lower()

            if not user_id or not platform:
                await self.send_text("缺少必要参数：user_id 和 platform")
                return False, "缺少必要参数"

            # 限制消息数量
            max_count = self.get_config("general.max_message_count", 100)
            message_count = min(message_count, max_count)

            # 查询聊天记录
            logger.info(f"{self.log_prefix} 查询用户 {user_id}@{platform} 的聊天记录，数量：{message_count}")

            with db:
                query = Messages.select().where(
                    (Messages.user_id == user_id) &
                    (Messages.user_platform == platform)
                ).order_by(Messages.time.desc()).limit(message_count)

                # 根据chat_type筛选
                if chat_type == "group":
                    query = query.where(Messages.chat_info_group_id.is_null(False))
                elif chat_type == "private":
                    query = query.where(Messages.chat_info_group_id.is_null(True))

                messages = list(query)

            if not messages:
                await self.send_text(f"未找到用户 {user_id} 的聊天记录")
                return False, "未找到聊天记录"

            # 反转消息顺序（从旧到新）
            messages.reverse()

            # 转换为截图所需格式
            screenshot_messages = []
            for msg in messages:
                # 格式化时间
                timestamp = datetime.fromtimestamp(msg.time).strftime("%Y-%m-%d %H:%M:%S")

                # 判断是否是机器人消息
                is_bot = (msg.user_id is None or msg.user_id == "")

                screenshot_messages.append({
                    'text': msg.processed_plain_text or msg.display_message or "",
                    'nickname': msg.user_nickname or "未知用户",
                    'timestamp': timestamp,
                    'is_bot': is_bot,
                    'user_id': msg.user_id or ""
                })

            # 生成截图
            logger.info(f"{self.log_prefix} 生成聊天记录截图，消息数：{len(screenshot_messages)}")

            style_config = {
                "screenshot_width": self.get_config("general.screenshot_width", 800),
                "font_size": self.get_config("general.font_size", 16),
                "background_color": self.get_config("style.background_color", "#F5F5F5"),
                "user_bubble_color": self.get_config("style.user_bubble_color", "#95EC69"),
                "bot_bubble_color": self.get_config("style.bot_bubble_color", "#FFFFFF"),
                "other_bubble_color": self.get_config("style.other_bubble_color", "#FFFFFF"),
                "text_color": self.get_config("style.text_color", "#000000"),
                "timestamp_color": self.get_config("style.timestamp_color", "#999999"),
                "bubble_radius": self.get_config("style.bubble_radius", 8),
                "message_spacing": self.get_config("style.message_spacing", 10),
                "show_timestamp": self.get_config("general.show_timestamp", True),
            }

            generator = ChatScreenshotGenerator(style_config)
            image_bytes = generator.generate_screenshot(screenshot_messages, user_id)

            # 保存截图
            screenshot_path = os.path.abspath(f"chat_screenshot_{user_id}_{int(time.time())}.png")
            with open(screenshot_path, "wb") as f:
                f.write(image_bytes)

            logger.info(f"{self.log_prefix} 截图已保存：{screenshot_path}")

            # 判断当前会话类型
            current_group_id = None
            if hasattr(self.message.message_info, 'group_info') and self.message.message_info.group_info:
                current_group_id = self.message.message_info.group_info.group_id
            is_current_group = current_group_id is not None

            # 发送截图
            result_msg = ""

            if send_to == "current":
                # 发送到当前会话
                await self.send_custom(message_type="imageurl", content=screenshot_path)
                result_msg = f"已生成聊天记录截图（共{len(screenshot_messages)}条消息）"

            elif send_to == "private":
                # 发送到私聊
                await self.send_custom(message_type="imageurl", content=screenshot_path)

                # 如果当前是群聊，则额外转发到私聊
                if is_current_group:
                    success = await CrossChatSender.send_to_private(
                        platform=platform,
                        user_id=user_id,
                        content=screenshot_path,
                        message_type="imageurl",
                        content_path=screenshot_path
                    )
                    result_msg = f"已生成聊天记录截图{'并发送到私聊' if success else '（发送到私聊失败）'}（共{len(screenshot_messages)}条消息）"
                else:
                    result_msg = f"已生成聊天记录截图（共{len(screenshot_messages)}条消息）"

            elif send_to == "group":
                # 发送到群聊
                await self.send_custom(message_type="imageurl", content=screenshot_path)

                # 如果当前是私聊，则额外转发到群聊
                if not is_current_group:
                    groups = await CrossChatSender.find_user_groups(platform, user_id)
                    if groups:
                        # 转发到第一个群
                        target_group = groups[0]
                        success = await CrossChatSender.send_to_group(
                            platform=platform,
                            group_id=target_group,
                            content=screenshot_path,
                            message_type="imageurl",
                            content_path=screenshot_path
                        )
                        result_msg = f"已生成聊天记录截图{'并发送到群聊' if success else '（发送到群聊失败）'}（共{len(screenshot_messages)}条消息）"
                    else:
                        result_msg = f"已生成聊天记录截图，但未找到该用户所在的群（共{len(screenshot_messages)}条消息）"
                else:
                    result_msg = f"已生成聊天记录截图（共{len(screenshot_messages)}条消息）"

            else:
                await self.send_custom(message_type="imageurl", content=screenshot_path)
                result_msg = f"已生成聊天记录截图（共{len(screenshot_messages)}条消息）"

            await self.store_action_info(
                action_build_into_prompt=True,
                action_prompt_display=f"生成了用户{user_id}的聊天记录截图（{len(screenshot_messages)}条消息）",
                action_done=True
            )

            return True, result_msg

        except Exception as e:
            error_msg = str(e)
            logger.error(f"{self.log_prefix} 生成聊天记录截图失败: {error_msg}", exc_info=True)
            await self.send_text(f"生成聊天记录截图失败: {error_msg}")
            return False, error_msg


class ChatScreenshotCommand(BaseCommand):
    """聊天记录截图Command - 用户手动触发"""

    command_name = "chat_screenshot_command"
    command_description = "截取聊天记录并生成截图"
    command_pattern = r"^/screenshot\s+(?P<count>\d+)?$"
    command_help = "截取聊天记录。用法：/screenshot [数量]"
    command_examples = [
        "/screenshot",
        "/screenshot 30"
    ]
    intercept_message = True

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行截图命令"""
        try:
            count_str = self.matched_groups.get("count", "20")
            message_count = int(count_str) if count_str else 20

            # 获取当前用户信息
            user_id = self.message.message_info.user_info.user_id
            platform = self.message.message_info.platform

            # 限制消息数量
            max_count = self.get_config("general.max_message_count", 100)
            message_count = min(message_count, max_count)

            # 查询聊天记录
            with db:
                messages = list(
                    Messages.select().where(
                        (Messages.user_id == user_id) &
                        (Messages.user_platform == platform)
                    ).order_by(Messages.time.desc()).limit(message_count)
                )

            if not messages:
                await self.send_text("未找到你的聊天记录")
                return False, "未找到聊天记录", True

            # 反转消息顺序
            messages.reverse()

            # 转换格式
            screenshot_messages = []
            for msg in messages:
                timestamp = datetime.fromtimestamp(msg.time).strftime("%Y-%m-%d %H:%M:%S")
                is_bot = (msg.user_id is None or msg.user_id == "")

                screenshot_messages.append({
                    'text': msg.processed_plain_text or msg.display_message or "",
                    'nickname': msg.user_nickname or "未知用户",
                    'timestamp': timestamp,
                    'is_bot': is_bot,
                    'user_id': msg.user_id or ""
                })

            # 生成截图
            style_config = {
                "screenshot_width": self.get_config("general.screenshot_width", 800),
                "font_size": self.get_config("general.font_size", 16),
                "background_color": self.get_config("style.background_color", "#F5F5F5"),
                "user_bubble_color": self.get_config("style.user_bubble_color", "#95EC69"),
                "bot_bubble_color": self.get_config("style.bot_bubble_color", "#FFFFFF"),
                "other_bubble_color": self.get_config("style.other_bubble_color", "#FFFFFF"),
                "text_color": self.get_config("style.text_color", "#000000"),
                "timestamp_color": self.get_config("style.timestamp_color", "#999999"),
                "bubble_radius": self.get_config("style.bubble_radius", 8),
                "message_spacing": self.get_config("style.message_spacing", 10),
                "show_timestamp": self.get_config("general.show_timestamp", True),
            }

            generator = ChatScreenshotGenerator(style_config)
            image_bytes = generator.generate_screenshot(screenshot_messages, user_id)

            # 保存并发送
            screenshot_path = os.path.abspath(f"chat_screenshot_{user_id}_{int(time.time())}.png")
            with open(screenshot_path, "wb") as f:
                f.write(image_bytes)

            await self.send_custom(message_type="imageurl", content=screenshot_path)

            return True, f"已生成聊天记录截图（共{len(screenshot_messages)}条消息）", True

        except Exception as e:
            logger.error(f"{self.log_prefix} 截图命令执行失败: {e}", exc_info=True)
            await self.send_text(f"截图失败: {e}")
            return False, f"执行失败: {e}", True


@register_plugin
class ChatScreenshotPlugin(BasePlugin):
    """聊天记录截图插件"""

    plugin_name = "chat_screenshot_plugin"
    plugin_description = "截取聊天记录并生成截图，用于举证或回顾历史对话"
    plugin_version = "1.0.0"
    plugin_author = "Assistant"
    enable_plugin = True
    config_file_name = "config.toml"
    dependencies = []
    python_dependencies = ["Pillow"]

    config_section_descriptions = {
        "plugin": "插件基本配置",
        "general": "通用设置",
        "components": "组件启用控制",
        "style": "截图样式配置"
    }

    config_schema = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "config_version": ConfigField(type=str, default="1.0.0", description="配置文件版本")
        },
        "general": {
            "default_message_count": ConfigField(type=int, default=20, description="默认截取消息数量"),
            "max_message_count": ConfigField(type=int, default=100, description="最大截取消息数量"),
            "screenshot_width": ConfigField(type=int, default=800, description="截图宽度（像素）"),
            "font_size": ConfigField(type=int, default=16, description="字体大小"),
            "show_timestamp": ConfigField(type=bool, default=True, description="是否显示时间戳"),
            "show_avatar": ConfigField(type=bool, default=True, description="是否显示头像")
        },
        "components": {
            "action_enabled": ConfigField(type=bool, default=True, description="是否启用Action组件"),
            "command_enabled": ConfigField(type=bool, default=True, description="是否启用Command组件")
        },
        "style": {
            "background_color": ConfigField(type=str, default="#F5F5F5", description="背景颜色"),
            "user_bubble_color": ConfigField(type=str, default="#95EC69", description="用户消息气泡颜色"),
            "bot_bubble_color": ConfigField(type=str, default="#FFFFFF", description="机器人消息气泡颜色"),
            "other_bubble_color": ConfigField(type=str, default="#FFFFFF", description="其他用户消息气泡颜色"),
            "text_color": ConfigField(type=str, default="#000000", description="文字颜色"),
            "timestamp_color": ConfigField(type=str, default="#999999", description="时间戳颜色"),
            "bubble_radius": ConfigField(type=int, default=8, description="气泡圆角半径"),
            "message_spacing": ConfigField(type=int, default=10, description="消息间距")
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件组件列表"""
        components = []

        try:
            action_enabled = self.get_config("components.action_enabled", True)
            command_enabled = self.get_config("components.command_enabled", True)
        except AttributeError:
            action_enabled = True
            command_enabled = True

        if action_enabled:
            components.append((ChatScreenshotAction.get_action_info(), ChatScreenshotAction))

        if command_enabled:
            components.append((ChatScreenshotCommand.get_command_info(), ChatScreenshotCommand))

        return components
