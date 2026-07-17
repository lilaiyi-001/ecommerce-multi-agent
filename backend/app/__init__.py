"""电商选品运营多智能体系统"""
import os
import sys
from pathlib import Path

# 将 lib 目录加入 sys.path（所有第三方包安装在此目录下）
# __file__ = D:\电商选品2\backend\app\__init__.py
_lib_path = str(Path(__file__).parent.parent / "lib")
if os.path.isdir(_lib_path) and _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)
