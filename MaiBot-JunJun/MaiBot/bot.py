"""兼容入口：与 bot_junjun 相同，转调 launch/junjun.py。详见 launch/README.md"""
import runpy
import sys
from pathlib import Path

if __name__ != "__main__":
    sys.exit(0)

runpy.run_path(str(Path(__file__).resolve().parent / "launch" / "junjun.py"), run_name="__main__")
