"""
亲密度惩罚系统 - MCP 工具

提供给大模型使用的工具，用于检测不良行为并减少亲密度
"""

import time
from typing import Optional, Dict, List
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("relationship_penalty")


class RelationshipPenalty:
    """亲密度惩罚系统"""

    # 惩罚规则
    PENALTY_RULES = {
        'insult': -10.0,              # 辱骂
        'harassment': -8.0,            # 骚扰
        'spam': -5.0,                  # 无脑复制/刷屏
        'unfriendly': -3.0,            # 不友善
        'inappropriate': -5.0,         # 不当内容
        'aggressive': -4.0,            # 攻击性言论
        'disrespect': -3.0,            # 不尊重
        'negative_attitude': -2.0,     # 消极态度
        'ignore_response': -1.0,       # 无视回复
        'cold_response': -0.5,         # 冷淡回复
    }

    # 严重程度等级
    SEVERITY_MULTIPLIER = {
        'minor': 0.5,      # 轻微
        'moderate': 1.0,   # 中等
        'severe': 1.5,     # 严重
        'extreme': 2.0,    # 极端
    }

    @staticmethod
    def apply_penalty(
        user_id: str,
        platform: str,
        penalty_type: str,
        severity: str = 'moderate',
        reason: str = "",
        evidence: str = ""
    ) -> Optional[Dict]:
        """
        应用亲密度惩罚

        参数:
            user_id: 用户ID
            platform: 平台
            penalty_type: 惩罚类型 (insult/harassment/spam/unfriendly等)
            severity: 严重程度 (minor/moderate/severe/extreme)
            reason: 惩罚原因
            evidence: 证据（触发惩罚的消息内容）

        返回:
            {
                'success': bool,
                'user_id': str,
                'nickname': str,
                'old_relationship': float,
                'new_relationship': float,
                'penalty_amount': float,
                'penalty_type': str,
                'severity': str,
                'reason': str,
                'warning_message': str  # 给用户的警告消息
            }
        """
        try:
            with db:
                # 获取用户信息
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    logger.warning(f"用户不存在: {user_id}@{platform}")
                    return None

                # 计算惩罚值
                base_penalty = RelationshipPenalty.PENALTY_RULES.get(
                    penalty_type,
                    -2.0  # 默认惩罚
                )

                severity_mult = RelationshipPenalty.SEVERITY_MULTIPLIER.get(
                    severity,
                    1.0
                )

                penalty_amount = base_penalty * severity_mult

                # 记录旧值
                old_relationship = user.relationship_value

                # 应用惩罚
                new_relationship = max(0, old_relationship + penalty_amount)
                user.relationship_value = new_relationship

                # 如果是严重违规，可能影响心情值
                if severity in ['severe', 'extreme']:
                    user.mood_value = max(0, user.mood_value - 10)

                # 如果处于恋爱状态且惩罚严重，可能"分手"
                if user.is_in_love and severity == 'extreme':
                    user.is_in_love = False
                    logger.warning(f"💔 用户 {user.nickname or user_id} 因严重违规导致关系破裂")

                user.save()

                # 获取关系等级
                from src.common.relationship_updater import RelationshipUpdater
                old_level = RelationshipUpdater.get_relationship_level(old_relationship)
                new_level = RelationshipUpdater.get_relationship_level(new_relationship)

                # 生成警告消息
                warning_message = RelationshipPenalty._generate_warning_message(
                    penalty_type,
                    severity,
                    new_relationship
                )

                # 记录重大惩罚（严重或极端级别）
                if severity in ['severe', 'extreme']:
                    logger.warning(
                        f"⚠️ [重大变故] 严重惩罚: {user.nickname or user_id} "
                        f"({old_relationship:.1f} -> {new_relationship:.1f}, {penalty_amount:.1f}) "
                        f"类型: {penalty_type}({severity}) - {reason}"
                    )
                    # 记录到历史
                    from src.common.relationship_history_manager import RelationshipHistoryManager
                    RelationshipHistoryManager.record_event(
                        user_id=user_id,
                        platform=platform,
                        event_type='penalty',
                        old_value=old_relationship,
                        new_value=new_relationship,
                        reason=f"{penalty_type}({severity}): {reason}",
                        details={'penalty_type': penalty_type, 'severity': severity}
                    )
                # 记录关系等级下降
                elif old_level != new_level:
                    logger.warning(
                        f"⚠️ [重大变故] 关系等级下降: {user.nickname or user_id} "
                        f"({old_level} -> {new_level}, 亲密度: {old_relationship:.1f} -> {new_relationship:.1f})"
                    )
                # 普通惩罚
                else:
                    logger.warning(
                        f"⚠️ 惩罚应用: {user.nickname or user_id} "
                        f"({old_relationship:.1f} -> {new_relationship:.1f}, {penalty_amount:.1f}) "
                        f"原因: {penalty_type}({severity}) - {reason}"
                    )

                return {
                    'success': True,
                    'user_id': user_id,
                    'nickname': user.nickname,
                    'old_relationship': old_relationship,
                    'new_relationship': new_relationship,
                    'penalty_amount': penalty_amount,
                    'penalty_type': penalty_type,
                    'severity': severity,
                    'reason': reason,
                    'warning_message': warning_message,
                    'relationship_broken': user.is_in_love == False and old_relationship >= 100
                }

        except Exception as e:
            logger.error(f"应用惩罚失败: {e}", exc_info=True)
            return None

    @staticmethod
    def _generate_warning_message(
        penalty_type: str,
        severity: str,
        current_relationship: float
    ) -> str:
        """生成警告消息"""

        # 根据惩罚类型生成消息
        messages = {
            'insult': [
                "你这样说话让我很难过...",
                "请不要用这种方式和我说话...",
                "我不喜欢被这样对待..."
            ],
            'harassment': [
                "你的行为让我感到不舒服...",
                "请停止这种行为...",
                "这样下去我们没法好好聊天了..."
            ],
            'spam': [
                "请不要刷屏...",
                "能好好聊天吗？",
                "这样复制粘贴没有意义..."
            ],
            'unfriendly': [
                "你今天心情不好吗？",
                "感觉你有点不友善...",
                "我们能好好说话吗？"
            ],
            'inappropriate': [
                "这个话题不太合适...",
                "我们换个话题吧...",
                "请注意你的言行..."
            ],
            'aggressive': [
                "你的语气有点激动...",
                "冷静一下好吗？",
                "我们心平气和地聊..."
            ],
            'disrespect': [
                "我希望得到尊重...",
                "请尊重我...",
                "这样说话不太好..."
            ],
            'negative_attitude': [
                "你今天好像很消极...",
                "要不要聊点开心的？",
                "别这么悲观嘛..."
            ],
            'ignore_response': [
                "你好像没在听我说话...",
                "我说的话你有在听吗？",
                "感觉你不太在意我的回复..."
            ],
            'cold_response': [
                "你今天好冷淡...",
                "是我做错什么了吗？",
                "感觉你不太想聊天..."
            ]
        }

        base_message = messages.get(penalty_type, ["请注意你的言行..."])[0]

        # 根据严重程度添加额外信息
        if severity == 'extreme':
            base_message += "\n这样下去我们的关系会破裂的..."
        elif severity == 'severe':
            base_message += "\n我真的很在意这件事..."
        elif current_relationship < 20:
            base_message += "\n我们的关系已经很疏远了..."

        return base_message

    @staticmethod
    def check_spam_pattern(
        user_id: str,
        platform: str,
        message_text: str,
        recent_messages: List[str]
    ) -> Optional[Dict]:
        """
        检测刷屏模式

        参数:
            user_id: 用户ID
            platform: 平台
            message_text: 当前消息
            recent_messages: 最近的消息列表（最多10条）

        返回:
            如果检测到刷屏，返回惩罚信息；否则返回 None
        """
        if not recent_messages:
            return None

        # 检测完全相同的消息
        identical_count = sum(1 for msg in recent_messages if msg == message_text)

        if identical_count >= 3:
            return RelationshipPenalty.apply_penalty(
                user_id=user_id,
                platform=platform,
                penalty_type='spam',
                severity='moderate',
                reason=f"重复发送相同消息 {identical_count} 次",
                evidence=message_text
            )

        # 检测短时间内大量消息
        if len(recent_messages) >= 8 and all(len(msg) < 10 for msg in recent_messages[-8:]):
            return RelationshipPenalty.apply_penalty(
                user_id=user_id,
                platform=platform,
                penalty_type='spam',
                severity='minor',
                reason="短时间内发送大量短消息",
                evidence=f"最近8条消息: {recent_messages[-8:]}"
            )

        return None


# MCP 工具定义
def mcp_apply_relationship_penalty(
    user_id: str,
    platform: str,
    penalty_type: str,
    severity: str = 'moderate',
    reason: str = ""
) -> Dict:
    """
    MCP 工具：应用亲密度惩罚

    大模型可以调用此工具来惩罚不良行为

    参数:
        user_id: 用户ID
        platform: 平台 (qq/wechat等)
        penalty_type: 惩罚类型
            - insult: 辱骂
            - harassment: 骚扰
            - spam: 刷屏
            - unfriendly: 不友善
            - inappropriate: 不当内容
            - aggressive: 攻击性
            - disrespect: 不尊重
            - negative_attitude: 消极态度
            - ignore_response: 无视回复
            - cold_response: 冷淡回复
        severity: 严重程度 (minor/moderate/severe/extreme)
        reason: 惩罚原因（供日志记录）

    返回:
        {
            'success': bool,
            'warning_message': str,  # 应该发送给用户的警告
            'penalty_applied': float,
            'new_relationship': float
        }

    示例:
        # 用户辱骂
        result = mcp_apply_relationship_penalty(
            user_id="123456",
            platform="qq",
            penalty_type="insult",
            severity="severe",
            reason="用户使用侮辱性词汇"
        )

        # 返回警告消息给用户
        if result['success']:
            send_message(result['warning_message'])
    """
    result = RelationshipPenalty.apply_penalty(
        user_id=user_id,
        platform=platform,
        penalty_type=penalty_type,
        severity=severity,
        reason=reason
    )

    if result:
        return {
            'success': True,
            'warning_message': result['warning_message'],
            'penalty_applied': result['penalty_amount'],
            'new_relationship': result['new_relationship'],
            'relationship_broken': result.get('relationship_broken', False)
        }
    else:
        return {
            'success': False,
            'warning_message': "处理失败",
            'penalty_applied': 0,
            'new_relationship': 0
        }


# 使用示例
if __name__ == "__main__":
    # 测试惩罚系统
    result = mcp_apply_relationship_penalty(
        user_id="test_user",
        platform="qq",
        penalty_type="insult",
        severity="severe",
        reason="测试辱骂检测"
    )

    print(f"成功: {result['success']}")
    print(f"警告消息: {result['warning_message']}")
    print(f"惩罚值: {result['penalty_applied']}")
    print(f"新亲密度: {result['new_relationship']}")
