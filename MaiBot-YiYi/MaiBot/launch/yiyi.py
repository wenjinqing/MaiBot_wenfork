"""
伊伊启动：`config/yiyi_bot_config.toml`，环境变量见根目录 `.env`（YIYI_*）；
若存在 `.env.yiyi` 会先加载（与旧根目录 bot.py 行为一致）。
"""
import asyncio
import os
import time
import platform
import traceback
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_ROOT)
script_dir = str(_ROOT)

from dotenv import load_dotenv
from rich.traceback import install
from src.common.logger import initialize_logging, get_logger, shutdown_logging

_env_yiyi = _ROOT / ".env.yiyi"
if _env_yiyi.exists():
    load_dotenv(str(_env_yiyi), override=True)

env_path = _ROOT / ".env"
template_env_path = _ROOT / "template" / "template.env"

if env_path.exists():
    load_dotenv(str(env_path), override=False)
else:
    try:
        if template_env_path.exists():
            shutil.copyfile(template_env_path, env_path)
            print("未找到.env，已从 template/template.env 自动创建")
            load_dotenv(str(env_path), override=False)
        else:
            print("未找到.env文件，也未找到模板 template/template.env")
            raise FileNotFoundError(".env 文件不存在，请创建并配置所需的环境变量")
    except Exception as e:
        print(f"自动创建 .env 失败: {e}")
        raise

os.environ["BOT_ID"] = "yiyi_bot"
os.environ["BOT_CONFIG"] = "config/yiyi_bot_config.toml"
os.environ["WEBUI_ENABLED"] = "false"
os.environ["DISABLE_LEGACY_SERVER"] = "true"

initialize_logging()
install(extra_lines=3)
logger = get_logger("main")

RESTART_EXIT_CODE = 42

if __name__ != "__main__":
    sys.exit(0)

from src.main import MainSystem  # noqa
from src.manager.async_task_manager import async_task_manager  # noqa

logger.info(f"已设置工作目录为: {script_dir}")
logger.info("=" * 60)
logger.info("启动伊伊机器人 (yiyi_bot) [launch/yiyi.py]")
logger.info("配置文件: config/yiyi_bot_config.toml（账号见 .env 中 YIYI_QQ_ACCOUNT）")
logger.info("=" * 60)

confirm_logger = get_logger("confirm")


def print_opensource_notice():
    from colorama import init, Fore, Style

    init()

    notice_lines = [
        "",
        f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}",
        f"{Fore.MAGENTA}  ★ MaiBot - 伊伊机器人 ★{Style.RESET_ALL}",
        f"{Fore.CYAN}{'─' * 70}{Style.RESET_ALL}",
        f"{Fore.YELLOW}  本项目是完全免费的开源软件，基于 GPL-3.0 协议发布{Style.RESET_ALL}",
        f"{Fore.WHITE}  如果有人向你「出售本软件」，你被骗了！{Style.RESET_ALL}",
        "",
        f"{Fore.WHITE}  官方仓库: {Fore.BLUE}https://github.com/MaiM-with-u/MaiBot {Style.RESET_ALL}",
        f"{Fore.WHITE}  官方文档: {Fore.BLUE}https://docs.mai-mai.org {Style.RESET_ALL}",
        f"{Fore.WHITE}  官方群聊: {Fore.BLUE}766798517{Style.RESET_ALL}",
        f"{Fore.CYAN}{'─' * 70}{Style.RESET_ALL}",
        f"{Fore.RED}  [警告] 将本软件作为「商品」倒卖、隐瞒开源性质均违反协议！{Style.RESET_ALL}",
        f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}",
        "",
    ]

    for line in notice_lines:
        print(line)


async def graceful_shutdown():
    try:
        logger.info("正在优雅关闭伊伊...")

        try:
            from src.webui.webui_server import get_webui_server

            webui_server = get_webui_server()
            if webui_server and webui_server._server:
                await webui_server.shutdown()
        except Exception as e:
            logger.warning(f"关闭 WebUI 服务器时出错: {e}")

        from src.plugin_system.core.events_manager import events_manager
        from src.plugin_system.base.component_types import EventType

        await events_manager.handle_mai_events(event_type=EventType.ON_STOP)

        await async_task_manager.stop_and_wait_all_tasks()

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

        logger.info("伊伊优雅关闭完成")

    except Exception as e:
        logger.error(f"伊伊关闭失败: {e}", exc_info=True)


def raw_main():
    if platform.system().lower() != "windows":
        time.tzset()  # type: ignore

    print_opensource_notice()

    logger.info("跳过EULA检查（伊伊专用启动文件）")

    return MainSystem()


def main():
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
            print("[伊伊] 事件循环已关闭")

        try:
            shutdown_logging()
        except Exception as e:
            print(f"关闭日志系统时出错: {e}")

        print("[伊伊] 准备退出...")
        os._exit(exit_code)


if __name__ == "__main__":
    main()
