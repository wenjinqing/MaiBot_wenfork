"""
ChatLoop 快速启动示例

这个脚本展示如何在实际的 MaiBot 系统中快速启动 ChatLoop
"""

import asyncio
from src.common.logger import get_logger
from src.chat_v2.loop.chat_loop import chat_loop_manager, ScheduledTask
from src.chat_v2.agent.unified_agent import UnifiedChatAgent
from src.chat.message_receive.chat_stream import get_chat_manager

logger = get_logger("quick_start_chat_loop")


async def setup_chat_loop_for_chat(chat_stream):
    """
    为指定的聊天设置 ChatLoop

    Args:
        chat_stream: ChatStream 实例
    """
    logger.info(f"为聊天 {chat_stream.stream_id} 设置 ChatLoop")

    # 创建 Agent
    agent = UnifiedChatAgent(chat_stream)

    # 创建 ChatLoop
    loop = chat_loop_manager.create_loop(
        chat_id=chat_stream.stream_id,
        agent=agent,
        chat_stream=chat_stream,
        loop_interval=5.0,  # 每 5 秒检查一次
        enable_proactive_speak=True,
        enable_scheduled_tasks=True,
        enable_observation=True
    )

    # 添加定时任务
    await setup_scheduled_tasks(loop, chat_stream)

    # 启动循环
    await loop.start()
    logger.info(f"✅ ChatLoop 已启动: {chat_stream.stream_id}")

    return loop


async def setup_scheduled_tasks(loop, chat_stream):
    """
    设置定时任务

    Args:
        loop: ChatLoop 实例
        chat_stream: ChatStream 实例
    """

    # 示例 1: 每天早上 9 点发送早安
    async def morning_greeting():
        try:
            await chat_stream.send_message("早上好！新的一天开始了！☀️")
            logger.info(f"[{chat_stream.stream_id}] 发送早安问候")
        except Exception as e:
            logger.error(f"发送早安问候失败: {e}")

    loop.add_scheduled_task(ScheduledTask(
        name="morning_greeting",
        callback=morning_greeting,
        cron_hour=9,
        cron_minute=0,
        enabled=True  # 可以通过配置控制是否启用
    ))

    # 示例 2: 每天晚上 21 点发送晚安
    async def night_greeting():
        try:
            await chat_stream.send_message("晚安！做个好梦！🌙")
            logger.info(f"[{chat_stream.stream_id}] 发送晚安问候")
        except Exception as e:
            logger.error(f"发送晚安问候失败: {e}")

    loop.add_scheduled_task(ScheduledTask(
        name="night_greeting",
        callback=night_greeting,
        cron_hour=21,
        cron_minute=0,
        enabled=True
    ))

    # 示例 3: 每小时检查一次空闲时间
    async def check_idle_time():
        try:
            idle_time = loop.observation_data.get("idle_time", 0)

            # 如果超过 2 小时没人说话
            if idle_time > 7200:
                logger.info(f"[{chat_stream.stream_id}] 检测到长时间空闲: {idle_time:.1f} 秒")
                # 这里可以触发主动发言
                # await chat_stream.send_message("好久没人说话了，大家都在忙吗？")
        except Exception as e:
            logger.error(f"检查空闲时间失败: {e}")

    loop.add_scheduled_task(ScheduledTask(
        name="check_idle_time",
        callback=check_idle_time,
        interval=3600,  # 每小时
        enabled=True
    ))

    logger.info(f"[{chat_stream.stream_id}] 已添加 {len(loop.scheduled_tasks)} 个定时任务")


async def start_chat_loops_for_active_chats():
    """
    为所有活跃的聊���启动 ChatLoop
    """
    logger.info("开始为活跃聊天启动 ChatLoop")

    chat_manager = get_chat_manager()

    # 获取所有活跃的聊天
    # 这里需要根据实际情况调整，比如只为最近 7 天活跃的聊天启动
    active_chats = []  # chat_manager.get_active_chats()

    if not active_chats:
        logger.warning("没有找到活跃的聊天，跳过 ChatLoop 启动")
        return

    logger.info(f"找到 {len(active_chats)} 个活跃聊天")

    # 为每个聊天启动 ChatLoop
    for chat in active_chats:
        try:
            await setup_chat_loop_for_chat(chat)
        except Exception as e:
            logger.error(f"为聊天 {chat.stream_id} 启动 ChatLoop 失败: {e}")

    logger.info(f"✅ ChatLoop 启动完成，共 {len(chat_loop_manager.loops)} 个循环")


async def stop_all_chat_loops():
    """
    停止所有 ChatLoop
    """
    logger.info("停止所有 ChatLoop")
    await chat_loop_manager.stop_all()
    logger.info("✅ 所有 ChatLoop 已停止")


async def main():
    """
    主函数 - 用于测试
    """
    logger.info("=" * 60)
    logger.info("ChatLoop 快速启动测试")
    logger.info("=" * 60)

    # 启动 ChatLoop
    await start_chat_loops_for_active_chats()

    # 运行一段时间
    logger.info("ChatLoop 运行中，按 Ctrl+C 停止")
    try:
        await asyncio.sleep(3600)  # 运行 1 小时
    except KeyboardInterrupt:
        logger.info("收到停止信号")

    # 停止 ChatLoop
    await stop_all_chat_loops()


if __name__ == "__main__":
    # 测试模式
    asyncio.run(main())
