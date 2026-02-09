"""
简单脚本：从 library 目录复制知识库文件到 data/openie/ 目录
不需要导入项目模块，可以直接运行
"""

import os
import shutil
from pathlib import Path

# 获取脚本所在目录和项目根目录
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent

# library 目录的可能位置
LIBRARY_PATHS = [
    PROJECT_ROOT.parent / "library",  # MaiM-with-u/library
    PROJECT_ROOT / "library",  # MaiBot/library
    Path.cwd() / "library",  # 当前目录/library
]

# 目标目录
TARGET_DIR = PROJECT_ROOT / "data" / "openie"


def find_library_dir():
    """查找 library 目录"""
    for path in LIBRARY_PATHS:
        abs_path = path.absolute()
        if abs_path.exists() and abs_path.is_dir():
            return abs_path
    return None


def copy_library_files(library_dir, target_dir):
    """复制知识库文件"""
    library_path = Path(library_dir)
    target_path = Path(target_dir)
    
    # 确保目标目录存在
    target_path.mkdir(parents=True, exist_ok=True)
    
    # 查找所有 openie.json 文件
    json_files = list(library_path.glob("*openie.json"))
    
    if not json_files:
        print(f"[错误] 在 {library_dir} 目录下未找到任何 openie.json 文件")
        return False, 0
    
    print(f"\n找到 {len(json_files)} 个知识库文件：")
    for file in json_files:
        print(f"  - {file.name}")
    
    print()
    copied_count = 0
    skipped_count = 0
    
    for source_file in json_files:
        target_file = target_path / source_file.name
        
        # 如果目标文件已存在，询问是否覆盖
        if target_file.exists():
            print(f"[警告] 目标文件已存在: {target_file.name}")
            response = input(f"   是否覆盖? (y/n, 默认n): ").strip().lower()
            if response != "y":
                print(f"   跳过: {source_file.name}")
                skipped_count += 1
                continue
        
        try:
            shutil.copy2(source_file, target_file)
            print(f"[成功] 已复制: {source_file.name}")
            copied_count += 1
        except Exception as e:
            print(f"[失败] 复制失败 {source_file.name}: {e}")
            return False, copied_count
    
    return True, copied_count, skipped_count


def main():
    """主函数"""
    print("=" * 60)
    print("知识库文件复制工具")
    print("=" * 60)
    print()
    
    # 查找 library 目录
    print("正在查找 library 目录...")
    library_dir = find_library_dir()
    
    if not library_dir:
        print("\n[错误] 未找到 library 目录！")
        print("\n请确保 library 目录位于以下位置之一：")
        for i, path in enumerate(LIBRARY_PATHS, 1):
            abs_path = path.absolute()
            print(f"  {i}. {abs_path}")
        print()
        print("或者手动指定 library 目录路径：")
        manual_path = input("请输入 library 目录路径（留空退出）: ").strip()
        if not manual_path:
            return
        manual_path_obj = Path(manual_path)
        if manual_path_obj.exists() and manual_path_obj.is_dir():
            library_dir = manual_path_obj.absolute()
        else:
            print(f"[错误] 路径不存在或不是目录: {manual_path}")
            return
    
    print(f"[成功] 找到 library 目录: {library_dir}")
    
    # 目标目录
    target_dir = TARGET_DIR.absolute()
    print(f"[成功] 目标目录: {target_dir}")
    print()
    
    # 确认操作
    print("这个操作会：")
    print(f"  将 {library_dir.name} 目录下的所有 openie.json 文件")
    print(f"  复制到 {target_dir}")
    print()
    confirm = input("确认继续？(y/n): ").strip().lower()
    if confirm != "y":
        print("操作已取消")
        return
    
    print()
    print("-" * 60)
    
    # 复制文件
    success, copied_count, skipped_count = copy_library_files(library_dir, target_dir)
    
    print("-" * 60)
    print()
    
    if success:
        print(f"[完成] 文件复制完成！")
        print(f"  - 已复制: {copied_count} 个文件")
        if skipped_count > 0:
            print(f"  - 已跳过: {skipped_count} 个文件")
        print()
        print("下一步操作：")
        print("  运行导入脚本导入知识库：")
        print(f"    python scripts/import_openie.py")
        print()
        print("  注意事项：")
        print("    - 导入过程会消耗大量资源和时间")
        print("    - 需要配置 LLM API（用于生成 Embedding）")
        print("    - 建议在配置较好的电脑上运行")
        print()
    else:
        print("[错误] 复制过程中出现错误")


if __name__ == "__main__":
    main()

