#!/usr/bin/env python3
"""
风哨 v1.0 — 测风塔数据自动化工具
入口文件
"""
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import main

if __name__ == "__main__":
    main()
