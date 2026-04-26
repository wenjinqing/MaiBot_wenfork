"""兼容入口：转调 launch/junjun.py。详见 launch/README.md"""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "launch" / "junjun.py"), run_name="__main__")
