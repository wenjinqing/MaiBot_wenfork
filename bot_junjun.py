"""
君君机器人启动文件
基于原始bot.py，专门用于启动君君
"""
import asyncio
import hashlib
import os
import time
import platform
import traceback
import shutil
import sys
from dotenv import load_dotenv
from pathlib import Path
from rich.traceback import install
from src.common.logger import initialize_logging, get_logger, shutdown_logging

# 设置工作目录为脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 设置环境变量，指定使用君君的配置
os.environ['BOT_ID'] = 'junjun_main'
os.environ['BOT_CONFIG'] = 'config/bot_config.toml'
os.environ['WEBUI_ENABLED'] = 'true'  # 启用君君的 WebUI
os.environ['WEBUI_MODE'] = 'production'  # WebUI 生产模式

env_path = Path(__file__).parent / ".env"
template_env_path = Path(__file__).parent / "template" / "template.env"

if env_path.exists():
    load_dotenv(str(env_path), override=True)
else:
    try:
        if template_env_path.exists():
            shutil.copyfile(template_env_path, env_path)
            print("未找到.env，已从 template/template.env 自动创建")
            load_dotenv(str(env_path), override=True)
        else:
            print("未找到.env文件，也未找到模板 template/template.env")
            raise FileNotFoundError(".env 文件不存在，请创建并配置所需的环境变量")
    except Exception as e:
        print(f"自动创建 .env 失败: {e}")
        raise

initialize_logging()
install(extra_lines=3)
logger = get_logger("main")

# 定义重启退出码
RESTART_EXIT_CODE = 42

# 检查是否是 Worker 进程
if __name__ != "__main__":
    sys.exit(0)

from src.main import MainSystem  # noqa
from src.manager.async_task_manager import async_task_manager  # noqa

logger.info(f"已设置工作目录为: {script_dir}")
logger.info("=" * 60)
logger.info("启动君君机器人 (junjun_main)")
logger.info("配置文件: config/bot_config.toml")
logger.info("=" * 60)

confirm_logger = get_logger("confirm")


def print_opensource_notice():
    """打印开源项目提示"""
    from colorama import init, Fore, Style

    init()

    notice_lines = [

    ]

    for line in notice_lines:
        print(line)


async def graceful_shutdown():
    try:
        logger.info("正在优雅关闭君君...")

        # 关闭 WebUI 服务器
        try:
            from src.webui.webui_server import get_webui_server

            webui_server = get_webui_server()
            if webui_server and webui_server._server:
                await webui_server.shutdown()
        except Exception as e:
            logger.warning(f"关闭 WebUI 服务器时出错: {e}")

        from src.plugin_system.core.events_manager import events_manager
        from src.plugin_system.base.component_types import EventType

        # 触发 ON_STOP 事件
        await events_manager.handle_mai_events(event_type=EventType.ON_STOP)

        # 停止所有异步任务
        await async_task_manager.stop_and_wait_all_tasks()

        # 获取所有剩余任务
        remaining_tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

        if remaining_tasks:
            logger.info(f"正在取消 {len(remaining_tasks)} 个剩余任务...")

            for task in remaining_tasks:
                if not task.done():
                    task.cancel()

            try:
                await asyncio.wait_for(asyncio.gather(*remaining_tasks, return_exceptions=True), timeout=15.0)
                logger.info("所有剩余任务已成功取消")
            except asyncio.TimeoutError:
                logger.warning("等待任务取消超时，强制继续关闭")
            except Exception as e:
                logger.error(f"等待任务取消时发生异常: {e}")

        logger.info("君君优雅关闭完成")

    except Exception as e:
        logger.error(f"君君关闭失败: {e}", exc_info=True)


def raw_main():
    if platform.system().lower() != "windows":
        time.tzset()  # type: ignore

    print_opensource_notice()


    return MainSystem()


def main():
    """主函数，前台运行君君"""
    exit_code = 0
    try:
        main_system = raw_main()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from src.common.logger import initialize_ws_handler

        initialize_ws_handler(loop)

        try:
            loop.run_until_complete(main_system.initialize())
            main_tasks = loop.create_task(main_system.schedule_tasks())
            loop.run_until_complete(main_tasks)

        except KeyboardInterrupt:
            logger.warning("收到中断信号，正在优雅关闭...")

            if "main_tasks" in locals() and main_tasks and not main_tasks.done():
                main_tasks.cancel()
                try:
                    loop.run_until_complete(main_tasks)
                except asyncio.CancelledError:
                    pass

            if loop and not loop.is_closed():
                try:
                    loop.run_until_complete(graceful_shutdown())
                except Exception as ge:
                    logger.error(f"优雅关闭时发生错误: {ge}")

    except SystemExit as e:
        if isinstance(e.code, int):
            exit_code = e.code
        else:
            exit_code = 1 if e.code else 0
        if exit_code == RESTART_EXIT_CODE:
            logger.info("收到重启信号，准备退出并请求重启...")

    except Exception as e:
        logger.error(f"主程序发生异常: {str(e)} {str(traceback.format_exc())}")
        exit_code = 1
    finally:
        if "loop" in locals() and loop and not loop.is_closed():
            loop.close()
            print("[君君] 事件循环已关闭")

        try:
            shutdown_logging()
        except Exception as e:
            print(f"关闭日志系统时出错: {e}")

        print("[君君] 准备退出...")
        os._exit(exit_code)


if __name__ == "__main__":
    main()
