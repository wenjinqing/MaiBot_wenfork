"""
美女图片模块 - 看看美女功能

支持查看美女图片
"""

import random
from typing import Tuple
from src.common.logger import get_logger
from src.plugin_system.base.base_action import BaseAction, ActionActivationType
from src.plugin_system.base.base_command import BaseCommand
from src.plugin_system.base.component_types import ChatMode

logger = get_logger("entertainment_plugin.body_part")

# 可用的图片class列表
AVAILABLE_CLASSES = [
    101,  # JKFUN
    102,  # 兔玩印画
    103,  # 喵写真
    104,  # 紧急企划
    105,  # 木花琳琳是勇者
    106,  # 少女秩序
    107,  # 耶米西奶露
    108,  # DISI第四印象
    109,  # DJAWA
    111,  # 少女映画
    112,  # 喵糖映画
    11001,  # 高质量JK
    11002,  # 日式
    11003,  # 小清新
]

# JK相关的class列表（101和11001）
JK_CLASSES = [
    101,   # JKFUN
    11001,  # 高质量JK
]


class BodyPartImageAction(BaseAction):
    """美女图片 Action 组件 - 智能图片获取"""

    action_name = "body_part_image_action"
    action_description = "从API获取现成的美女图片并发送（不是AI绘图，是获取已存在的图片）"

    # 激活设置
    activation_type = ActionActivationType.KEYWORD
    mode_enable = ChatMode.ALL
    parallel_action = False

    # 关键词激活（优先匹配，避免与AI绘图工具冲突）
    activation_keywords = ["看看美女", "看美女", "康康美女", "每日一图", "每日好图", "今日美图"]
    keyword_case_sensitive = False
    
    # 在模块加载时记录关键词（用于调试）
    logger.info(f"BodyPartImageAction 已注册，激活关键词: {activation_keywords}, 支持模式: {ChatMode.ALL}")

    # Action 参数
    action_parameters = {}
    action_require = [
        "当用户要求看美女图片时使用",
        "当用户说'看看美女'、'看美女'、'康康美女'时使用",
        "当用户说'每日一图'、'每日好图'、'今日美图'时使用（这些是获取随机美女图片，不是AI绘图）",
        "当需要发送美女图片时使用",
        "注意：这不是AI绘图功能，而是从API获取现成的美女图片"
    ]
    associated_types = ["image"]

    async def execute(self) -> Tuple[bool, str]:
        """执行看看美女图片获取"""
        try:
            # 添加调试日志
            logger.info(
                f"{self.log_prefix} 看看美女Action被触发 - 群聊: {self.is_group}, "
                f"群ID: {self.group_id}, 用户: {self.user_nickname}({self.user_id})"
            )
            
            # 从配置获取设置
            base_url = self.get_config(
                "body_part.api_url",
                "https://www.onexiaolaji.cn/RandomPicture/api/"
            )
            api_key = self.get_config("body_part.api_key", "qq249663924")
            
            # 获取可用的class列表（从配置或使用默认值）
            available_classes = self.get_config(
                "body_part.available_classes",
                AVAILABLE_CLASSES
            )

            if not available_classes:
                logger.warning(f"{self.log_prefix} 可用class列表为空，使用默认列表")
                available_classes = AVAILABLE_CLASSES

            # 随机选择一个 class
            random_class = random.choice(available_classes)
            api_url = f"{base_url}?key={api_key}&class={random_class}"

            logger.info(
                f"{self.log_prefix} 开始获取美女图片，使用 class={random_class}, URL: {api_url}"
            )

            # 先发送文字标题，再发送图片
            title = "看吧！涩批！"
            await self.send_text(title)
            await self.send_custom("imageurl", api_url)
            
            logger.info(
                f"{self.log_prefix} 美女图片发送成功 (class={random_class})，标题: {title}"
            )
            return True, f"成功获取并发送美女图片 (类型{random_class})"

        except Exception as e:
            logger.error(f"{self.log_prefix} 看看美女图片获取出错: {e}", exc_info=True)
            await self.send_text(f"❌ 图片获取出错: {e}")
            return False, f"图片获取出错: {e}"


class BodyPartImageCommand(BaseCommand):
    """美女图片 Command - 手动图片获取命令"""

    command_name = "body_part_image_command"
    command_description = "获取美女图片，支持指定类型"

    # 命令匹配模式：/看看美女 [class] 或 /看美女 [class]
    command_pattern = r"^/(看看美女|看美女)(?:\s+(?P<class_param>\d+))?$"
    command_help = "获取美女图片。用法：/看看美女 [类型] 或 /看美女 [类型]，类型可选"
    command_examples = [
        "/看看美女",
        "/看美女 101",
        "/看看美女 11001"
    ]
    intercept_message = True

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行看看美女命令"""
        try:
            # 从配置获取设置
            base_url = self.get_config(
                "body_part.api_url",
                "https://www.onexiaolaji.cn/RandomPicture/api/"
            )
            api_key = self.get_config("body_part.api_key", "qq249663924")
            
            # 获取可用的class列表（从配置或使用默认值）
            available_classes = self.get_config(
                "body_part.available_classes",
                AVAILABLE_CLASSES
            )

            # 解析命令参数
            specified_class = self.matched_groups.get("class_param")

            if specified_class:
                # 用户指定了 class，直接使用
                selected_class = int(specified_class)
                logger.info(f"用户指定 class={selected_class}")
            else:
                # 用户未指定 class，随机选择
                selected_class = random.choice(available_classes)
                logger.info(f"随机选择 class={selected_class}")

            api_url = f"{base_url}?key={api_key}&class={selected_class}"
            logger.info(f"执行看看美女命令，使用 class={selected_class}")

            # 先发送文字标题，再发送图片
            title = "看吧！涩批！"
            await self.send_text(title)
            await self.send_custom("imageurl", api_url)
            return True, f"成功获取并发送美女图片 (类型{selected_class})", True

        except Exception as e:
            logger.error(f"看看美女命令执行出错: {e}")
            await self.send_text(f"❌ 图片获取出错: {e}")
            return False, f"图片获取出错: {e}", True


class JKImageAction(BaseAction):
    """JK图片 Action 组件 - 智能图片获取"""

    action_name = "jk_image_action"
    action_description = "获取JK图片并发送"

    # 激活设置
    activation_type = ActionActivationType.KEYWORD
    mode_enable = ChatMode.ALL
    parallel_action = False

    # 关键词激活
    activation_keywords = ["看看JK", "看JK", "康康JK"]
    keyword_case_sensitive = False
    
    # 在模块加载时记录关键词（用于调试）
    logger.info(f"JKImageAction 已注册，激活关键词: {activation_keywords}, 支持模式: {ChatMode.ALL}")

    # Action 参数
    action_parameters = {}
    action_require = [
        "当用户要求看JK图片时使用",
        "当用户说'看看JK'时使用",
        "当需要发送JK图片时使用"
    ]
    associated_types = ["image"]

    async def execute(self) -> Tuple[bool, str]:
        """执行看看JK图片获取"""
        try:
            # 从配置获取设置
            base_url = self.get_config(
                "body_part.api_url",
                "https://www.onexiaolaji.cn/RandomPicture/api/"
            )
            api_key = self.get_config("body_part.api_key", "qq249663924")
            
            # 获取JK相关的class列表（从配置或使用默认值）
            jk_classes = self.get_config(
                "body_part.jk_classes",
                JK_CLASSES
            )

            # 随机选择一个 class
            random_class = random.choice(jk_classes)
            api_url = f"{base_url}?key={api_key}&class={random_class}"

            logger.info(
                f"{self.log_prefix} 开始获取JK图片，使用 class={random_class}"
            )

            # 先发送文字标题，再发送图片
            title = "看吧！涩批！"
            await self.send_text(title)
            await self.send_custom("imageurl", api_url)
            
            logger.info(
                f"{self.log_prefix} JK图片发送成功 (class={random_class})，标题: {title}"
            )
            return True, f"成功获取并发送JK图片 (类型{random_class})"

        except Exception as e:
            logger.error(f"{self.log_prefix} 看看JK图片获取出错: {e}")
            await self.send_text(f"❌ 图片获取出错: {e}")
            return False, f"图片获取出错: {e}"


class JKImageCommand(BaseCommand):
    """JK图片 Command - 手动图片获取命令"""

    command_name = "jk_image_command"
    command_description = "获取JK图片，支持指定类型"

    # 命令匹配模式：/看看JK [class] 或 /看JK [class]
    command_pattern = r"^/(看看JK|看JK|康康JK)(?:\s+(?P<class_param>\d+))?$"
    command_help = "获取JK图片。用法：/看看JK [类型] 或 /看JK [类型]，类型可选（101或11001）"
    command_examples = [
        "/看看JK",
        "/看JK 101",
        "/看看JK 11001"
    ]
    intercept_message = True

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行看看JK命令"""
        try:
            # 从配置获取设置
            base_url = self.get_config(
                "body_part.api_url",
                "https://www.onexiaolaji.cn/RandomPicture/api/"
            )
            api_key = self.get_config("body_part.api_key", "qq249663924")
            
            # 获取JK相关的class列表（从配置或使用默认值）
            jk_classes = self.get_config(
                "body_part.jk_classes",
                JK_CLASSES
            )

            # 解析命令参数
            specified_class = self.matched_groups.get("class_param")

            if specified_class:
                # 用户指定了 class，验证是否为JK相关的class
                selected_class = int(specified_class)
                if selected_class not in jk_classes:
                    await self.send_text(f"❌ 指定的类型 {selected_class} 不是JK类型，JK类型为：{jk_classes}")
                    return False, f"无效的JK类型: {selected_class}", True
                logger.info(f"用户指定JK class={selected_class}")
            else:
                # 用户未指定 class，随机选择
                selected_class = random.choice(jk_classes)
                logger.info(f"随机选择JK class={selected_class}")

            api_url = f"{base_url}?key={api_key}&class={selected_class}"
            logger.info(f"执行看看JK命令，使用 class={selected_class}")

            # 先发送文字标题，再发送图片
            title = "看吧！涩批！"
            await self.send_text(title)
            await self.send_custom("imageurl", api_url)
            return True, f"成功获取并发送JK图片 (类型{selected_class})", True

        except Exception as e:
            logger.error(f"看看JK命令执行出错: {e}")
            await self.send_text(f"❌ 图片获取出错: {e}")
            return False, f"图片获取出错: {e}", True
