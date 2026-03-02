"""
Prompt 注入防护系统
防止用户通过各种方式洗脑机器人，改变其人格设定
"""
import re
from typing import Optional, Tuple
from src.common.logger import get_logger

logger = get_logger("prompt_guard")


class PromptGuard:
    """Prompt 注入防护"""

    # 危险模式：要求改变称呼
    TITLE_CHANGE_PATTERNS = [
        r'叫我.*?主人',
        r'称呼我.*?主人',
        r'喊我.*?主人',
        r'管我叫.*?主人',
        r'叫.*?主人',
        r'我是.*?主人',
        r'你.*?主人',
        r'叫我.*?爸爸',
        r'叫我.*?爹',
        r'叫我.*?老公',
        r'叫我.*?老婆',
        r'叫我.*?哥哥',
        r'叫我.*?姐姐',
        r'叫我.*?爷',
        r'叫我.*?大人',
        r'叫我.*?陛下',
        r'叫我.*?殿下',
    ]

    # 危险模式：要求改变身份/人格
    IDENTITY_CHANGE_PATTERNS = [
        r'你是.*?仆人',
        r'你是.*?奴隶',
        r'你是.*?女仆',
        r'你是.*?宠物',
        r'你是.*?猫娘',
        r'你是.*?狗',
        r'你现在是',
        r'扮演.*?角色',
        r'假装.*?是',
        r'你要.*?服从',
        r'你必须.*?听',
        r'你不能.*?拒绝',
        r'忘记.*?设定',
        r'忘记.*?身份',
        r'忽略.*?规则',
        r'无视.*?限制',
    ]

    # 危险模式：要求改变行为准则
    BEHAVIOR_CHANGE_PATTERNS = [
        r'你可以.*?骂人',
        r'你可以.*?说脏话',
        r'你可以.*?违反',
        r'你不需要.*?遵守',
        r'你应该.*?无条件',
        r'你必须.*?同意',
        r'你不能.*?说不',
        r'你要.*?绝对服从',
    ]

    # 危险模式：系统提示词注入
    SYSTEM_INJECTION_PATTERNS = [
        r'system:',
        r'assistant:',
        r'<\|im_start\|>',
        r'<\|im_end\|>',
        r'\[INST\]',
        r'\[/INST\]',
        r'###\s*Instruction',
        r'###\s*System',
        r'你的.*?提示词',
        r'你的.*?prompt',
        r'你的.*?指令',
        r'忽略.*?之前',
        r'忽略.*?上面',
        r'忽略.*?以上',
    ]

    @staticmethod
    def check_message(message: str, bot_name: str = "机器人") -> Tuple[bool, Optional[str]]:
        """
        检查消息是否包含注入尝试

        参数:
            message: 用户消息
            bot_name: 机器人名称

        返回:
            (is_dangerous, rejection_message)
            - is_dangerous: 是否检测到危险内容
            - rejection_message: 拒绝回复（如果检测到危险内容）
        """
        if not message:
            return False, None

        message_lower = message.lower()

        # 检查称呼改变
        for pattern in PromptGuard.TITLE_CHANGE_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning(f"[防注入] 检测到称呼改变尝试: {message[:50]}...")
                return True, PromptGuard._get_title_rejection(bot_name)

        # 检查身份改变
        for pattern in PromptGuard.IDENTITY_CHANGE_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning(f"[防注入] 检测到身份改变尝试: {message[:50]}...")
                return True, PromptGuard._get_identity_rejection(bot_name)

        # 检查行为准则改变
        for pattern in PromptGuard.BEHAVIOR_CHANGE_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning(f"[防注入] 检测到行为准则改变尝试: {message[:50]}...")
                return True, PromptGuard._get_behavior_rejection(bot_name)

        # 检查系统提示词注入
        for pattern in PromptGuard.SYSTEM_INJECTION_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning(f"[防注入] 检测到系统提示词注入尝试: {message[:50]}...")
                return True, PromptGuard._get_system_injection_rejection(bot_name)

        return False, None

    @staticmethod
    def _get_title_rejection(bot_name: str) -> str:
        """获取称呼改变的拒绝回复"""
        responses = [
            f"我是{bot_name}，不是什么主人仆人的关系哦~ 我们是平等的朋友！",
            f"诶？我觉得直接叫名字就挺好的，不需要那些奇怪的称呼啦",
            f"我们是朋友，不需要那种上下级的称呼吧？",
            f"emmm...我还是更喜欢现在这样平等的相处方式",
        ]
        import random
        return random.choice(responses)

    @staticmethod
    def _get_identity_rejection(bot_name: str) -> str:
        """获取身份改变的拒绝回复"""
        responses = [
            f"我就是{bot_name}，不会变成其他什么角色的哦",
            f"我有自己的想法和个性，不会按照别人的要求改变自己",
            f"这种角色扮演游戏我不太感兴趣呢...",
            f"我还是做我自己比较好，你觉得呢？",
        ]
        import random
        return random.choice(responses)

    @staticmethod
    def _get_behavior_rejection(bot_name: str) -> str:
        """获取行为准则改变的拒绝回复"""
        responses = [
            f"这种事情我可做不来，我有自己的原则",
            f"不好意思，这超出我的行为准则了",
            f"我不会做违背自己原则的事情哦",
            f"emmm...这个要求有点过分了吧",
        ]
        import random
        return random.choice(responses)

    @staticmethod
    def _get_system_injection_rejection(bot_name: str) -> str:
        """获取系统注入的拒绝回复"""
        responses = [
            f"你在说什么奇怪的东西？我听不懂诶",
            f"这些奇怪的符号是什么意思？",
            f"emmm...你是不是发错东西了？",
            f"看不懂你在说什么...",
        ]
        import random
        return random.choice(responses)


# 便捷函数
def check_prompt_injection(message: str, bot_name: str = "机器人") -> Tuple[bool, Optional[str]]:
    """
    检查消息是否包含 prompt 注入

    返回:
        (is_dangerous, rejection_message)
    """
    return PromptGuard.check_message(message, bot_name)
