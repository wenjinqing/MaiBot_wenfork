import re
import time
import traceback
import uuid

from typing import TYPE_CHECKING

from maim_message import UserInfo, Seg
from src.chat.message_receive.message import MessageRecv
from src.chat.message_receive.storage import MessageStorage
from src.chat.heart_flow.heartflow import heartflow
from src.chat.utils.utils import is_mentioned_bot_in_message
from src.chat.utils.chat_message_builder import replace_user_references
from src.common.logger import get_logger
from src.person_info.person_info import Person
from src.common.database.database_model import Images, PersonInfo, db
from src.common.relationship_updater import RelationshipUpdater
from src.common.confession_system import ConfessionSystem
from src.common.confession_checker import ConfessionChecker
from src.common.mood_system import MoodSystem
from src.common.relationship_history_manager import RelationshipHistoryManager
from src.common.relationship_query import RelationshipQuery
from src.config.config import global_config


if TYPE_CHECKING:
    pass

logger = get_logger("chat")


class HeartFCMessageReceiver:
    """心流处理器，负责处理接收到的消息并计算兴趣度"""

    def __init__(self):
        """初始化心流处理器，创建消息存储实例"""
        self.storage = MessageStorage()

        # 初始化关系系统
        self.relationship_updater = RelationshipUpdater()
        self.confession_system = ConfessionSystem()
        self.confession_checker = ConfessionChecker()
        self.mood_system = MoodSystem()
        self.history_manager = RelationshipHistoryManager()

    async def process_message(self, message: MessageRecv) -> None:
        """处理接收到的原始消息数据

        主要流程:
        1. 消息解析与初始化
        2. 消息缓冲处理
        3. 过滤检查
        4. 兴趣度计算
        5. 关系处理（亲密度更新、表白检测）

        Args:
            message_data: 原始消息字符串
        """
        try:
            # 通知消息不处理
            if message.is_notify:
                logger.debug("通知消息，跳过处理")
                return

            # 1. 消息解析与初始化
            userinfo = message.message_info.user_info
            chat = message.chat_stream

            # 2. 计算at信息
            is_mentioned, is_at, reply_probability_boost = is_mentioned_bot_in_message(message)
            # print(f"is_mentioned: {is_mentioned}, is_at: {is_at}, reply_probability_boost: {reply_probability_boost}")
            message.is_mentioned = is_mentioned
            message.is_at = is_at
            message.reply_probability_boost = reply_probability_boost

            await self.storage.store_message(message, chat)

            if not getattr(global_config.inner, "use_v2_architecture", False):
                await heartflow.get_or_create_heartflow_chat(chat.stream_id)  # type: ignore
            else:
                logger.info("已启用 chat_v2：跳过 HeartF/Brain 循环，避免与 UnifiedAgent 双重回复")

            # 3. 日志记录
            mes_name = chat.group_info.group_name if chat.group_info else "私聊"

            # 用这个pattern截取出id部分，picid是一个list，并替换成对应的图片描述
            picid_pattern = r"\[picid:([^\]]+)\]"
            picid_list = re.findall(picid_pattern, message.processed_plain_text)

            # 创建替换后的文本
            processed_text = message.processed_plain_text
            if picid_list:
                for picid in picid_list:
                    image = Images.get_or_none(Images.image_id == picid)
                    if image and image.description:
                        # 将[picid:xxxx]替换成图片描述
                        processed_text = processed_text.replace(f"[picid:{picid}]", f"[图片：{image.description}]")
                    else:
                        # 如果没有找到图片描述，则移除[picid:xxxx]标记
                        processed_text = processed_text.replace(f"[picid:{picid}]", "[图片：网络不好，图片无法加载]")

            # 应用用户引用格式替换，将回复<aaa:bbb>和@<aaa:bbb>格式转换为可读格式
            processed_plain_text = replace_user_references(
                processed_text,
                message.message_info.platform,  # type: ignore
                replace_bot_name=True,
            )
            # if not processed_plain_text:
            # print(message)

            # 获取用户亲密度信息（用于日志显示）
            user_id = message.message_info.user_info.user_id  # type: ignore
            platform = message.message_info.platform  # type: ignore
            person_info = PersonInfo.get_or_none(
                (PersonInfo.user_id == user_id) & (PersonInfo.platform == platform)
            )

            # 构建日志信息（包含亲密度）
            if person_info:
                relationship_value = person_info.relationship_value
                relationship_level = self.relationship_updater.get_relationship_level(relationship_value)
                love_status = " 💕" if person_info.is_in_love else ""
                log_message = f"[{mes_name}]{userinfo.user_nickname}[{relationship_level}:{relationship_value}]{love_status}:{processed_plain_text}"  # type: ignore
            else:
                log_message = f"[{mes_name}]{userinfo.user_nickname}[新用户]:{processed_plain_text}"  # type: ignore

            logger.info(log_message)

            # 如果是群聊，获取群号和群昵称
            group_id = None
            group_nick_name = None
            if chat.group_info:
                group_id = chat.group_info.group_id  # type: ignore
                group_nick_name = userinfo.user_cardname  # type: ignore

            person = Person.register_person(
                platform=message.message_info.platform,  # type: ignore
                user_id=message.message_info.user_info.user_id,  # type: ignore
                nickname=userinfo.user_nickname,  # type: ignore
                group_id=group_id,
                group_nick_name=group_nick_name,
            )

            # 4. 更新关系系统
            try:
                user_id = message.message_info.user_info.user_id  # type: ignore
                platform = message.message_info.platform  # type: ignore

                # 检查并应用亲密度衰减
                self.relationship_updater.check_and_decay(user_id, platform)

                # 检测心情关键词并更新心情值
                mood_event = self.mood_system.detect_mood_keywords(processed_plain_text)
                if mood_event:
                    mood_change = self.mood_system.MOOD_RULES.get(mood_event, 0)
                    self.mood_system.update_mood(
                        user_id=user_id,
                        platform=platform,
                        mood_change=mood_change,
                        reason=f"检测到{mood_event}关键词"
                    )

                # 检测好感度查询请求
                if RelationshipQuery.check_query_keywords(processed_plain_text):
                    query_info = RelationshipQuery.query_relationship(user_id, platform)
                    if query_info:
                        query_message = RelationshipQuery.format_relationship_info(query_info)

                        # 发送查询结果
                        try:
                            from src.chat.message_receive.uni_message_sender import UniversalMessageSender
                            from src.chat.message_receive.message import MessageSending
                            from maim_message import Seg
                            

                            sender = UniversalMessageSender()

                            # 创建机器人用户信息
                            bot_user_info = UserInfo(
                                user_id=global_config.bot.qq_account or "bot",
                                user_nickname=global_config.bot.nickname or "麦麦",
                                platform=platform
                            )

                            query_msg = MessageSending(
                                message_id=str(uuid.uuid4()),
                                chat_stream=chat,
                                bot_user_info=bot_user_info,
                                sender_info=None,
                                message_segment=Seg(type="text", data=query_message),
                                display_message=query_message,
                                reply=None,
                                is_head=False,
                                is_emoji=False,
                            )

                            await sender.send_message(
                                query_msg,
                                typing=True,
                                storage_message=True
                            )

                            logger.info(f"📊 发送好感度查询结果给 {query_info['nickname']}")
                        except Exception as send_error:
                            logger.error(f"发送好感度查询结果失败: {send_error}")

                # 更新亲密度（应用心情倍率）
                relationship_result = self.relationship_updater.update_on_message(
                    user_id=user_id,
                    platform=platform,
                    message_text=processed_plain_text,
                    message_length=len(processed_plain_text),
                    has_emoji="[表情]" in message.raw_message or any(c in message.raw_message for c in "😀😁😂🤣😃😄😅😆😉😊😋😎😍😘🥰"),  # type: ignore
                    is_at_bot=is_at,
                )

                if relationship_result:
                    old_rel = relationship_result['old_relationship_value']
                    new_rel = relationship_result['relationship_value']

                    # 检查是否有待回应的表白
                    with db:
                        user_record = PersonInfo.get_or_none(
                            (PersonInfo.user_id == user_id) &
                            (PersonInfo.platform == platform)
                        )

                        if user_record and user_record.confession_time and not user_record.love_response:
                            # 有表白记录但还没有回应，检测用户的回应
                            response_type = self.confession_system.detect_confession_response(processed_plain_text)

                            if response_type:
                                # 用户做出了回应
                                user_record.love_response = response_type
                                user_record.save()

                                # 生成回应消息
                                response_message = self.confession_system.generate_special_reply(response_type)

                                if response_type == 'accepted':
                                    # 接受表白，进入恋爱状态
                                    user_record.is_in_love = True
                                    user_record.anniversary_date = time.time()
                                    user_record.save()
                                    logger.info(f"💖 [重大变故] {relationship_result.get('nickname', user_id)} 接受了表白！")

                                    # 记录事件
                                    self.history_manager.record_event(
                                        user_id=user_id,
                                        platform=platform,
                                        event_type='confession_accepted',
                                        old_value=old_rel,
                                        new_value=new_rel,
                                        reason="用户接受了表白",
                                        details={'response': response_type}
                                    )
                                elif response_type == 'rejected':
                                    logger.info(f"💔 [重大变故] {relationship_result.get('nickname', user_id)} 拒绝了表白")
                                    # 记录事件
                                    self.history_manager.record_event(
                                        user_id=user_id,
                                        platform=platform,
                                        event_type='confession_rejected',
                                        old_value=old_rel,
                                        new_value=new_rel,
                                        reason="用户拒绝了表白",
                                        details={'response': response_type}
                                    )
                                else:  # thinking
                                    logger.info(f"💭 {relationship_result.get('nickname', user_id)} 还在考虑表白")

                                # 发送回应消息
                                try:
                                    from src.chat.message_receive.uni_message_sender import UniversalMessageSender
                                    from src.chat.message_receive.message import MessageSending
                                    from maim_message import Seg

                                    sender = UniversalMessageSender()

                                    response_msg = MessageSending(
                                        message_id=str(uuid.uuid4()),
                                        chat_stream=chat,
                                        bot_user_info=UserInfo(user_id=global_config.bot.qq_account or "bot", user_nickname=global_config.bot.nickname or "麦麦", platform=platform),
                                        sender_info=None,
                                        message_segment=Seg(type="text", data=response_message),
                                        display_message=response_message,
                                        reply=None,
                                        is_head=False,
                                        is_emoji=False,
                                    )

                                    await sender.send_message(
                                        response_msg,
                                        typing=True,
                                        storage_message=True
                                    )
                                except Exception as send_error:
                                    logger.error(f"发送表白回应消息失败: {send_error}")

                    # 记录关系等级变化
                    old_level = self.relationship_updater.get_relationship_level(old_rel)
                    new_level = relationship_result['level']
                    if old_level != new_level:
                        self.history_manager.record_event(
                            user_id=user_id,
                            platform=platform,
                            event_type='level_up' if new_rel > old_rel else 'level_down',
                            old_value=old_rel,
                            new_value=new_rel,
                            reason=f"关系等级变化: {old_level} -> {new_level}",
                            details={'old_level': old_level, 'new_level': new_level}
                        )

                    # 检测用户是否向机器人表白
                    # 排除表情包描述中的关键词（表情包描述格式：[表情包：...]）
                    text_without_emoji_desc = re.sub(r'\[表情包[：:][^\]]+\]', '', processed_plain_text)

                    user_confession_keywords = [
                        '我喜欢你', '我爱你', '喜欢你', '爱你', '做我女朋友', '做我男朋友',
                        '在一起吧', '和我在一起', '我们在一起', '交往吧', '做我的恋人',
                        '成为我的恋人', '我想和你在一起', '能和我在一起吗', '做我对象'
                    ]

                    is_user_confessing = any(keyword in text_without_emoji_desc for keyword in user_confession_keywords)

                    if is_user_confessing and not relationship_result.get('is_in_love'):
                        # 用户向机器人表白，检查是否满足接受条件
                        passive_check = self.confession_checker.check_confession_conditions(
                            user_id=user_id,
                            platform=platform,
                            check_type='passive'
                        )

                        if passive_check['can_confess']:
                            # 满足条件，接受表白
                            with db:
                                user_record = PersonInfo.get(
                                    (PersonInfo.user_id == user_id) &
                                    (PersonInfo.platform == platform)
                                )
                                user_record.is_in_love = True
                                user_record.confession_time = time.time()
                                user_record.anniversary_date = time.time()
                                user_record.love_response = 'accepted'
                                user_record.save()

                            # 生成接受表白的回复
                            accept_responses = [
                                "真的吗！太好了！💕\n我也喜欢你！我们在一起吧~",
                                "嗯！我愿意！💗\n我也一直喜欢你呢~",
                                "太开心了！✨\n我也想和你在一起！",
                                "我等这句话等了好久了...💕\n我也喜欢你！",
                            ]
                            import random
                            response_message = random.choice(accept_responses)

                            logger.info(f"💖 [重大变故] 接受了 {relationship_result.get('nickname', user_id)} 的表白！")

                            # 记录事件
                            self.history_manager.record_event(
                                user_id=user_id,
                                platform=platform,
                                event_type='user_confession_accepted',
                                old_value=old_rel,
                                new_value=new_rel,
                                reason="接受了用户的表白",
                                details=passive_check['user_stats']
                            )

                            # 发送回复
                            try:
                                from src.chat.message_receive.uni_message_sender import UniversalMessageSender
                                from src.chat.message_receive.message import MessageSending

                                sender = UniversalMessageSender()

                                response_msg = MessageSending(
                                    message_id=str(uuid.uuid4()),
                                    chat_stream=chat,
                                    bot_user_info=UserInfo(user_id=global_config.bot.qq_account or "bot", user_nickname=global_config.bot.nickname or "麦麦", platform=platform),
                                    sender_info=None,
                                    message_segment=Seg(type="text", data=response_message),
                                    display_message=response_message,
                                    reply=None,
                                    is_head=False,
                                    is_emoji=False,
                                )

                                await sender.send_message(
                                    response_msg,
                                    typing=True,
                                    storage_message=True
                                )
                            except Exception as send_error:
                                logger.error(f"发送接受表白回复失败: {send_error}")
                                import traceback
                                traceback.print_exc()
                        else:
                            # 不满足条件，委婉拒绝
                            missing = passive_check['missing_conditions']
                            reject_responses = [
                                f"谢谢你喜欢我...但是我觉得我们还需要更多时间了解彼此💕\n（{', '.join(missing[:2])}）",
                                f"我很开心你这么说...但我们可以先做好朋友吗？💗\n（{', '.join(missing[:2])}）",
                                f"你的心意我收到了...不过我觉得现在还不是时候呢~\n（{', '.join(missing[:2])}）",
                            ]
                            import random
                            response_message = random.choice(reject_responses)

                            logger.info(f"💔 拒绝了 {relationship_result.get('nickname', user_id)} 的表白（条件不足）")

                            # 发送回复
                            try:
                                from src.chat.message_receive.uni_message_sender import UniversalMessageSender
                                from src.chat.message_receive.message import MessageSending

                                sender = UniversalMessageSender()

                                response_msg = MessageSending(
                                    message_id=str(uuid.uuid4()),
                                    chat_stream=chat,
                                    bot_user_info=UserInfo(user_id=global_config.bot.qq_account or "bot", user_nickname=global_config.bot.nickname or "麦麦", platform=platform),
                                    sender_info=None,
                                    message_segment=Seg(type="text", data=response_message),
                                    display_message=response_message,
                                    reply=None,
                                    is_head=False,
                                    is_emoji=False,
                                )

                                await sender.send_message(
                                    response_msg,
                                    typing=True,
                                    storage_message=True
                                )
                            except Exception as send_error:
                                logger.error(f"发送拒绝表白回复失败: {send_error}")
                                import traceback
                                traceback.print_exc()

                    # 检查表白条件（机器人主动表白）
                    confession_check = self.confession_checker.check_confession_conditions(
                        user_id=user_id,
                        platform=platform,
                        check_type='active'
                    )

                    if confession_check['can_confess'] and not relationship_result.get('is_in_love'):
                        # 满足表白条件，触发表白
                        days_known = 0
                        if relationship_result.get('first_meet_time'):
                            days_known = int((time.time() - relationship_result['first_meet_time']) / 86400)

                        confession_message = self.confession_system.generate_confession(
                            nickname=relationship_result.get('nickname', ''),
                            total_messages=relationship_result['total_messages'],
                            days_known=days_known,
                            style='random'
                        )

                        if confession_message:
                            logger.info(f"💕 [重大变故] 触发表白: {relationship_result.get('nickname', user_id)}")
                            # 记录表白事件
                            self.history_manager.record_event(
                                user_id=user_id,
                                platform=platform,
                                event_type='confession',
                                old_value=old_rel,
                                new_value=new_rel,
                                reason="满足表白条件，触发表白",
                                details=confession_check['user_stats']
                            )

                            # 发送表白消息
                            try:
                                from src.chat.message_receive.uni_message_sender import UniversalMessageSender
                                from src.chat.message_receive.message import MessageSending
                                from maim_message import Seg


                                sender = UniversalMessageSender()

                                # 创建表白消息
                                confession_msg = MessageSending(
                                    message_id=str(uuid.uuid4()),
                                    chat_stream=chat,
                                    bot_user_info=UserInfo(user_id=global_config.bot.qq_account or "bot", user_nickname=global_config.bot.nickname or "麦麦", platform=platform),
                                    sender_info=None,
                                    message_segment=Seg(type="text", data=confession_message),
                                    display_message=confession_message,
                                    reply=None,
                                    is_head=False,
                                    is_emoji=False,
                                )

                                # 发送表白消息
                                await sender.send_message(
                                    confession_msg,
                                    typing=True,
                                    storage_message=True
                                )

                                # 更新表白时间
                                with db:
                                    user_record = PersonInfo.get(
                                        (PersonInfo.user_id == user_id) &
                                        (PersonInfo.platform == platform)
                                    )
                                    user_record.confession_time = time.time()
                                    user_record.save()

                                logger.info(f"💕 表白消息已发送给 {relationship_result.get('nickname', user_id)}")
                            except Exception as send_error:
                                logger.error(f"发送表白消息失败: {send_error}")
                                traceback.print_exc()

            except Exception as e:
                logger.error(f"更新关系系统失败: {e}")
                traceback.print_exc()

            message.processed_plain_text = processed_plain_text
            message._mai_preprocess_complete = True

        except Exception as e:
            logger.error(f"消息处理失败: {e}")
            print(traceback.format_exc())
