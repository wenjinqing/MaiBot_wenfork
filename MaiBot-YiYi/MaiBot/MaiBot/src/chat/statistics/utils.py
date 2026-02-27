"""统计模块工具函数"""
from datetime import timedelta


def format_online_time(online_seconds: int) -> str:
    """
    格式化在线时间
    :param online_seconds: 在线时间（秒）
    :return: 格式化后的在线时间字符串
    """
    total_online_time = timedelta(seconds=online_seconds)

    days = total_online_time.days
    hours = total_online_time.seconds // 3600
    minutes = (total_online_time.seconds // 60) % 60
    seconds = total_online_time.seconds % 60
    if days > 0:
        # 如果在线时间超过1天，则格式化为"X天X小时X分钟"
        return f"{total_online_time.days}天{hours}小时{minutes}分钟{seconds}秒"
    elif hours > 0:
        # 如果在线时间超过1小时，则格式化为"X小时X分钟X秒"
        return f"{hours}小时{minutes}分钟{seconds}秒"
    else:
        # 其他情况格式化为"X分钟X秒"
        return f"{minutes}分钟{seconds}秒"


def format_large_number(num: float | int, html: bool = False) -> str:
    """
    格式化大数字，使用K后缀节省空间（大于9999时）
    :param num: 要格式化的数字
    :param html: 是否用于HTML输出（如果是，K会着色）
    :return: 格式化后的字符串，如 12K, 1.3K, 120K
    """
    if num >= 10000:
        # 大于等于10000，使用K后缀
        value = num / 1000.0
        if value >= 10:
            number_part = str(int(value))
            k_suffix = "K"
        else:
            number_part = f"{value:.1f}"
            k_suffix = "K"

        if html:
            # HTML输出：K着色为主题色并加粗大写
            return f"{number_part}<span style='color: #8b5cf6; font-weight: bold;'>K</span>"
        else:
            # 控制台输出：纯文本，K大写
            return f"{number_part}{k_suffix}"
    else:
        # 小于10000，直接显示
        if isinstance(num, float):
            return f"{num:.1f}" if num != int(num) else str(int(num))
        else:
            return str(num)
