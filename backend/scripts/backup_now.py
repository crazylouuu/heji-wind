# -*- coding: utf-8 -*-
"""手动/计划任务触发的备份入口。

用法：
    backend\\venv\\Scripts\\python backend\\scripts\\backup_now.py

也可配合 Windows 计划任务实现"系统级每日备份"（不依赖服务是否在运行）。
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
sys.path.insert(0, BASE)

# 输出编码守卫：本脚本面向用户控制台，保持系统编码（Windows 通常 GBK/cp936），
# 只放宽不可编码字符。若强行改用 UTF-8，经 cmd 的 GBK 控制台会显示成乱码。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

from utils.auto_backup import run_backup, prune_backups, get_settings


def main():
    cfg = get_settings()
    try:
        info = run_backup("manual")
    except Exception as e:
        print(f"备份失败: {type(e).__name__}: {e}")
        return 1
    removed = prune_backups(cfg["keep"])
    size_mb = info["size"] / 1024 / 1024
    print(f"备份完成: {info['name']}")
    print(f"  大小: {size_mb:.2f} MB | 附件: {info['attachments']} 个")
    print(f"  位置: {os.path.dirname(info['path'])}")
    if removed:
        print(f"  已清理旧备份: {len(removed)} 份（保留 {cfg['keep']} 份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
