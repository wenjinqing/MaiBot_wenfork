"""机器人管理 API 路由"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from src.common.logger import get_logger
from src.core import get_message_router, BotInstance, BotStatus
from src.config.config import global_config
from src.config.official_configs import BotInstanceConfig

logger = get_logger("webui.bot_management")

# 创建路由器
router = APIRouter(prefix="/bots", tags=["Bot Management"])


# ==================== 数据模型 ====================

class BotStatusResponse(BaseModel):
    """机器人状态响应"""
    bot_id: str = Field(..., description="机器人ID")
    nickname: str = Field(..., description="机器人昵称")
    qq_account: str = Field(..., description="QQ账号")
    status: str = Field(..., description="运行状态")
    enabled: bool = Field(..., description="是否启用")
    error_message: Optional[str] = Field(None, description="错误信息")
    message_count: int = Field(0, description="处理消息数")
    start_time: Optional[float] = Field(None, description="启动时间")
    uptime: Optional[float] = Field(None, description="运行时长（秒）")
    last_message_time: Optional[float] = Field(None, description="最后消息时间")


class BotStatisticsResponse(BaseModel):
    """机器人统计信息响应"""
    bot_id: str = Field(..., description="机器人ID")
    nickname: str = Field(..., description="机器人昵称")
    status: str = Field(..., description="运行状态")
    message_count: int = Field(0, description="处理消息数")
    uptime: Optional[float] = Field(None, description="运行时长（秒）")

    # 数据库统计
    person_count: int = Field(0, description="用户数量")
    chat_stream_count: int = Field(0, description="聊天流数量")
    message_db_count: int = Field(0, description="消息数量")
    expression_count: int = Field(0, description="表达方式数量")
    jargon_count: int = Field(0, description="黑话数量")


class BotListResponse(BaseModel):
    """机器人列表响应"""
    total: int = Field(..., description="机器人总数")
    bots: List[BotStatusResponse] = Field(..., description="机器人列表")


class BotControlRequest(BaseModel):
    """机器人控制请求"""
    bot_id: str = Field(..., description="机器人ID")


class BotControlResponse(BaseModel):
    """机器人控制响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
    bot_id: str = Field(..., description="机器人ID")


class RouterStatisticsResponse(BaseModel):
    """路由器统计信息响应"""
    total_bots: int = Field(..., description="机器人总数")
    running_bots: int = Field(..., description="运行中的机器人数")
    total_messages: int = Field(..., description="总消息数")
    failed_routes: int = Field(..., description="路由失败数")
    bots: List[Dict[str, Any]] = Field(..., description="机器人列表")


# ==================== 辅助函数 ====================

def get_bot_instance(bot_id: str) -> BotInstance:
    """获取机器人实例"""
    router = get_message_router()
    bot_instance = router.get_bot_by_id(bot_id)

    if not bot_instance:
        raise HTTPException(status_code=404, detail=f"机器人 {bot_id} 不存在")

    return bot_instance


def check_multi_bot_enabled():
    """检查是否启用多机器人模式"""
    if not global_config.enable_multi_bot:
        raise HTTPException(
            status_code=400,
            detail="多机器人模式未启用，请在配置文件中设置 enable_multi_bot = true"
        )


# ==================== API 端点 ====================

@router.get("/list", response_model=BotListResponse)
async def list_bots():
    """
    获取所有机器人列表

    返回所有已注册的机器人及其状态信息
    """
    try:
        router = get_message_router()
        bot_instances_dict = router.get_all_bots()

        bots = []
        for bot_instance in bot_instances_dict.values():
            status_info = bot_instance.get_status_info()
            bots.append(BotStatusResponse(**status_info))

        return BotListResponse(
            total=len(bots),
            bots=bots
        )

    except Exception as e:
        logger.error(f"获取机器人列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取机器人列表失败: {str(e)}")


@router.get("/{bot_id}/status", response_model=BotStatusResponse)
async def get_bot_status(bot_id: str):
    """
    获取指定机器人的状态

    Args:
        bot_id: 机器人ID

    Returns:
        机器人状态信息
    """
    try:
        bot_instance = get_bot_instance(bot_id)
        status_info = bot_instance.get_status_info()

        return BotStatusResponse(**status_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取机器人状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取机器人状态失败: {str(e)}")


@router.get("/{bot_id}/statistics", response_model=BotStatisticsResponse)
async def get_bot_statistics(bot_id: str):
    """
    获取指定机器人的统计信息

    Args:
        bot_id: 机器人ID

    Returns:
        机器人统计信息（包括数据库统计）
    """
    try:
        bot_instance = get_bot_instance(bot_id)
        statistics = bot_instance.get_statistics()

        return BotStatisticsResponse(**statistics)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取机器人统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取机器人统计信息失败: {str(e)}")


@router.post("/{bot_id}/start", response_model=BotControlResponse)
async def start_bot(bot_id: str):
    """
    启动指定的机器人

    Args:
        bot_id: 机器人ID

    Returns:
        操作结果
    """
    try:
        bot_instance = get_bot_instance(bot_id)

        if bot_instance.status == BotStatus.RUNNING:
            return BotControlResponse(
                success=False,
                message=f"机器人 {bot_id} 已在运行中",
                bot_id=bot_id
            )

        await bot_instance.start()

        logger.info(f"机器人 {bot_id} 已启动")
        return BotControlResponse(
            success=True,
            message=f"机器人 {bot_id} 启动成功",
            bot_id=bot_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动机器人失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动机器人失败: {str(e)}")


@router.post("/{bot_id}/stop", response_model=BotControlResponse)
async def stop_bot(bot_id: str):
    """
    停止指定的机器人

    Args:
        bot_id: 机器人ID

    Returns:
        操作结果
    """
    try:
        bot_instance = get_bot_instance(bot_id)

        if bot_instance.status == BotStatus.STOPPED:
            return BotControlResponse(
                success=False,
                message=f"机器人 {bot_id} 已停止",
                bot_id=bot_id
            )

        await bot_instance.stop()

        logger.info(f"机器人 {bot_id} 已停止")
        return BotControlResponse(
            success=True,
            message=f"机器人 {bot_id} 停止成功",
            bot_id=bot_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止机器人失败: {e}")
        raise HTTPException(status_code=500, detail=f"停止机器人失败: {str(e)}")


@router.post("/{bot_id}/restart", response_model=BotControlResponse)
async def restart_bot(bot_id: str):
    """
    重启指定的机器人

    Args:
        bot_id: 机器人ID

    Returns:
        操作结果
    """
    try:
        bot_instance = get_bot_instance(bot_id)

        await bot_instance.restart()

        logger.info(f"机器人 {bot_id} 已重启")
        return BotControlResponse(
            success=True,
            message=f"机器人 {bot_id} 重启成功",
            bot_id=bot_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重启机器人失败: {e}")
        raise HTTPException(status_code=500, detail=f"重启机器人失败: {str(e)}")


@router.get("/router/statistics", response_model=RouterStatisticsResponse)
async def get_router_statistics():
    """
    获取消息路由器的统计信息

    Returns:
        路由器统计信息
    """
    try:
        router = get_message_router()
        statistics = router.get_router_statistics()

        return RouterStatisticsResponse(**statistics)

    except Exception as e:
        logger.error(f"获取路由器统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取路由器统计信息失败: {str(e)}")


@router.get("/config/multi-bot-enabled")
async def check_multi_bot_status():
    """
    检查多机器人模式是否启用

    Returns:
        多机器人模式状态
    """
    return {
        "enabled": global_config.enable_multi_bot,
        "message": "多机器人模式已启用" if global_config.enable_multi_bot else "多机器人模式未启用"
    }
