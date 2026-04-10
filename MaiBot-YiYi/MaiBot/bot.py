"""兼容入口：与旧版一致默认启动伊伊，转调 launch/yiyi.py。君君请用 launch/junjun.py 或 bot_junjun.py。详见 launch/README.md"""
import runpy
import sys
from pathlib import Path

if __name__ != "__main__":
    sys.exit(0)

runpy.run_path(str(Path(__file__).resolve().parent / "launch" / "yiyi.py"), run_name="__main__")
