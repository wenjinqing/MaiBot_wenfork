"""
好感度查询动作
允许用户通过关键词查询自己的好感度信息
使用大模型生成自然的回复
"""

from src.plugin_system.base import BaseAction
from src.common.relationship_query import RelationshipQuery
from src.common.logger import get_logger
from src.llm_models.utils_model import LLMRequest
from src.config.config import model_config, global_config

logger = get_logger("好感度查询")


class IntimacyQueryAction(BaseAction):
    """好感度查询动作"""

    action_name = "intimacy_query"
    action_description = "查询用户的好感度信息"
    action_priority = 100  # 高优先级，优先处理

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化 LLM 请求器
        self.llm_request = LLMRequest(
            model_set=model_config.model_task_config.replyer,
            request_type="intimacy_query.reply"
        )

    async def check(self) -> bool:
        """检查是否触发好感度查询"""
        message_text = self.component.message_info.message_text
        return RelationshipQuery.check_query_keywords(message_text)

    async def execute(self) -> tuple[bool, str, bool]:
        """执行好感度查询"""
        try:
            user_id = self.component.message_info.user_info.user_id
            platform = self.component.message_info.platform
            user_nickname = self.component.message_info.user_info.user_nickname

            # 查询好感度信息
            info = RelationshipQuery.query_relationship(user_id, platform)

            if not info:
                # 没有记录时，让大模型生成自然的回复
                prompt = self._build_no_record_prompt(user_nickname)
                response, _ = await self.llm_request.generate_response_async(
                    prompt=prompt,
                    temperature=0.8,
                    max_tokens=150,
                )
                await self.send_text(response.strip())
                return True, "查询成功（无记录）", True

            # 有记录时，让大模型根据好感度信息生成自然的回复
            prompt = self._build_intimacy_reply_prompt(user_nickname, info)
            response, _ = await self.llm_request.generate_response_async(
                prompt=prompt,
                temperature=0.8,
                max_tokens=300,
            )

            await self.send_text(response.strip())
            logger.info(f"用户 {user_id} 查询了好感度信息 (好感度: {info['relationship_value']:.1f})")
            return True, "查询成功", True

        except Exception as e:
            logger.error(f"好感度查询失败: {e}", exc_info=True)
            await self.send_text("查询好感度时出错了，请稍后再试~")
            return False, f"查询失败: {e}", True

    def _build_no_record_prompt(self, user_nickname: str) -> str:
        """构建无记录时的提示词"""
        return f"""你是{global_config.bot.nickname}，{global_config.personality.personality}

你的说话风格：{global_config.personality.reply_style}

【情况】
{user_nickname} 向你询问好感度，但是你还没有关于 ta 的好感度记录（可能是刚认识，或者还没有建立关系记录）。

【任务】
用你自己的话语，自然地告诉 {user_nickname} 这个情况，并鼓励 ta 多和你聊天。

【要求】
1. 语气要友好、可爱，符合你的猫娘性格
2. 可以适度使用猫娘语气词（如"喵"、"呜"等），但不要过度
3. 不要使用生硬的模板语言
4. 2-3句话即可，简短自然
5. 可以有点小傲娇，但要保持可爱
6. 表达出想和对方多聊天、增进了解的意思

直接输出你想说的话，不要有任何前缀、解释或引号："""

    def _build_intimacy_reply_prompt(self, user_nickname: str, info: dict) -> str:
        """构建有好感度记录时的提示词"""

        relationship_level = info['relationship_level']
        relationship_value = info['relationship_value']
        mood_value = info['mood_value']
        total_messages = info['total_messages']
        is_in_love = info['is_in_love']
        memory_points = info.get('memory_points', [])

        # 根据好感度生成关系描述
        if relationship_value >= 90:
            intimacy_desc = "非常亲密的挚友"
        elif relationship_value >= 70:
            intimacy_desc = "关系很好的朋友"
        elif relationship_value >= 50:
            intimacy_desc = "比较熟悉的熟人"
        elif relationship_value >= 30:
            intimacy_desc = "刚认识不久的朋友"
        else:
            intimacy_desc = "还不太熟悉"

        # 根据心情值生成心情描述
        if mood_value >= 90:
            mood_desc = "非常开心"
        elif mood_value >= 75:
            mood_desc = "心情很好"
        elif mood_value >= 60:
            mood_desc = "心情不错"
        elif mood_value >= 40:
            mood_desc = "心情一般"
        elif mood_value >= 25:
            mood_desc = "有点低落"
        else:
            mood_desc = "心情不太好"

        # 恋人关系特殊处理
        love_status = ""
        if is_in_love:
            love_status = f"\n- 重要：{user_nickname} 是你的恋人！"

        # 格式化印象记录
        memory_str = ""
        if memory_points and isinstance(memory_points, list):
            formatted = []
            for m in memory_points[:5]:
                parts = str(m).split(":", 2)
                if len(parts) >= 2:
                    formatted.append(f"  - {parts[0]}：{parts[1]}")
                else:
                    formatted.append(f"  - {m}")
            if formatted:
                memory_str = "\n- 你对 ta 的印象：\n" + "\n".join(formatted)

        return f"""你是{global_config.bot.nickname}，{global_config.personality.personality}

你的说话风格：{global_config.personality.reply_style}

【情况】
{user_nickname} 向你询问好感度。以下是你们的关系信息：

**关系数据：**
- 好感度：{relationship_value:.1f}/100
- 关系等级：{relationship_level}（{intimacy_desc}）
- 你对 ta 的心情：{mood_value}/100（{mood_desc}）
- 聊天次数：{total_messages} 条消息{love_status}{memory_str}

【任务】
用你自己的话语，自然地告诉 {user_nickname} 你们的关系情况，并自然地分享你对 ta 的印象。

【要求】
1. 用自然、口语化的方式表达，不要使用生硬的数据报告格式
2. 可以提到好感度数值，但要用自然的方式说出来
3. 如果有印象记录，把对 ta 的了解自然地融入回复中，不要逐条列举
4. 根据关系等级调整语气：挚友/恋人更亲密，熟人友好保持距离，陌生礼貌鼓励交流
5. 如果是恋人关系，一定要表现出特别的亲密和温柔
6. 适度使用猫娘语气词，不要每句都用
7. 3-5句话即可，不要太长

直接输出你想说的话，不要有任何前缀、解释或引号："""
