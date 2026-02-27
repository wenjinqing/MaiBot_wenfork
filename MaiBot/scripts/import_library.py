"""
从 library 目录导入知识库文件到项目

这个脚本会：
1. 将 library 目录下的所有 openie.json 文件复制到 data/openie/ 目录
2. 运行知识库导入脚本
"""

import sys
import os
import shutil
from pathlib import Path

# 添加项目根目录到 sys.path
ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT_PATH)

from src.common.logger import get_logger, initialize_logging

# 初始化日志系统
initialize_logging()
logger = get_logger("导入知识库")


def find_library_dir():
    """查找 library 目录"""
    # 可能的 library 目录位置
    possible_paths = [
        # library 在同级的 MaiM-with-u 目录下
        os.path.join(ROOT_PATH, "..", "library"),
        # library 在项目根目录
        os.path.join(ROOT_PATH, "library"),
        # library 在当前工作目录
        os.path.join(os.getcwd(), "library"),
    ]
    
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path) and os.path.isdir(abs_path):
            return abs_path
    
    return None


def copy_library_files(library_dir, target_dir):
    """复制 library 目录下的所有 openie.json 文件到目标目录"""
    library_path = Path(library_dir)
    target_path = Path(target_dir)
    
    # 确保目标目录存在
    target_path.mkdir(parents=True, exist_ok=True)
    
    # 查找所有 openie.json 文件
    json_files = list(library_path.glob("*openie.json"))
    
    if not json_files:
        logger.error(f"在 {library_dir} 目录下未找到任何 openie.json 文件")
        return False, 0
    
    logger.info(f"找到 {len(json_files)} 个知识库文件：")
    for file in json_files:
        logger.info(f"  - {file.name}")
    
    # 复制文件
    copied_count = 0
    for source_file in json_files:
        target_file = target_path / source_file.name
        
        # 如果目标文件已存在，询问是否覆盖
        if target_file.exists():
            logger.warning(f"目标文件已存在: {target_file.name}")
            response = input(f"是否覆盖 {target_file.name}? (y/n): ").strip().lower()
            if response != "y":
                logger.info(f"跳过文件: {source_file.name}")
                continue
        
        try:
            shutil.copy2(source_file, target_file)
            logger.info(f"✓ 已复制: {source_file.name}")
            copied_count += 1
        except Exception as e:
            logger.error(f"✗ 复制失败 {source_file.name}: {e}")
            return False, copied_count
    
    return True, copied_count


def main():
    """主函数"""
    print("=" * 60)
    print("知识库导入工具")
    print("=" * 60)
    print()
    
    # 查找 library 目录
    logger.info("正在查找 library 目录...")
    library_dir = find_library_dir()
    
    if not library_dir:
        logger.error("未找到 library 目录！")
        logger.error("请确保 library 目录位于以下位置之一：")
        logger.error("  1. MaiBot/../library (MaiM-with-u/library)")
        logger.error("  2. MaiBot/library")
        logger.error("  3. 当前工作目录/library")
        print()
        print("你可以手动指定 library 目录路径：")
        manual_path = input("请输入 library 目录路径（留空退出）: ").strip()
        if not manual_path:
            sys.exit(1)
        if os.path.exists(manual_path) and os.path.isdir(manual_path):
            library_dir = os.path.abspath(manual_path)
        else:
            logger.error(f"路径不存在或不是目录: {manual_path}")
            sys.exit(1)
    
    logger.info(f"找到 library 目录: {library_dir}")
    
    # 目标目录
    target_dir = os.path.join(ROOT_PATH, "data", "openie")
    logger.info(f"目标目录: {target_dir}")
    print()
    
    # 确认操作
    print("这个操作会：")
    print(f"  1. 将 {library_dir} 目录下的所有 openie.json 文件复制到 {target_dir}")
    print(f"  2. 然后你可以运行导入脚本来导入知识库")
    print()
    confirm = input("确认继续？(y/n): ").strip().lower()
    if confirm != "y":
        logger.info("操作已取消")
        sys.exit(0)
    
    print()
    print("-" * 60)
    
    # 复制文件
    success, copied_count = copy_library_files(library_dir, target_dir)
    
    print("-" * 60)
    print()
    
    if success and copied_count > 0:
        logger.info(f"✓ 成功复制 {copied_count} 个知识库文件")
        print()
        print("下一步操作：")
        print("  1. 运行导入脚本导入知识库：")
        print("     python scripts/import_openie.py")
        print()
        print("  注意事项：")
        print("    - 导入过程会消耗大量资源和时间")
        print("    - 需要配置 LLM API（用于生成 Embedding）")
        print("    - 建议在配置较好的电脑上运行")
        print()
    elif copied_count == 0:
        logger.warning("没有文件被复制")
    else:
        logger.error("复制过程中出现错误")
        sys.exit(1)


if __name__ == "__main__":
    main()

















