# -*- coding: utf-8 -*-
"""安全备份 — 把 backend/data 物理备份到**项目外**。

为什么需要它：项目内的 data/backups 与被备份的数据库在同一目录树里，
一旦发生误删、git 破坏性操作、磁盘故障，备份会与源数据一起丢失。
本脚本把数据复制到项目外的独立目录，实现真正的异地备份。

用法：
    双击项目根目录的「安全备份.bat」
    或：backend\\venv\\Scripts\\python backend\\scripts\\safe_backup.py
"""
import os
import shutil
import sys
import zipfile
from datetime import datetime

# 输出编码守卫：保持系统编码（Windows 通常 GBK/cp936），只放宽不可编码字符。
# 若强行改用 UTF-8，经 cmd 的 GBK 控制台会显示成乱码。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend/
PROJECT = os.path.dirname(BACKEND)                                      # 项目根
DATA_DIR = os.path.join(BACKEND, "data")
DB_PATH = os.path.join(DATA_DIR, "chemeln.db")
ATTACH_DIR = os.path.join(DATA_DIR, "attachments")

# 备份目标：项目外的独立目录（刻意不放项目内）
BACKUP_ROOT = os.path.join(os.path.dirname(PROJECT), "chemeln-backups")
KEEP = 10  # 保留最近份数


def main():
    if not os.path.exists(DB_PATH):
        print(f"[错误] 数据库不存在: {DB_PATH}")
        return 1

    os.makedirs(BACKUP_ROOT, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(BACKUP_ROOT, f"chemeln_data_{stamp}.zip")

    n_attach = 0
    try:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.write(DB_PATH, "chemeln.db")
            if os.path.isdir(ATTACH_DIR):
                for root, _dirs, files in os.walk(ATTACH_DIR):
                    for fn in files:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, ATTACH_DIR)
                        z.write(full, os.path.join("attachments", rel))
                        n_attach += 1
    except Exception as e:
        print(f"[错误] 备份失败: {type(e).__name__}: {e}")
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        return 1

    size_kb = os.path.getsize(out_path) / 1024
    # 同时保留一份「当前」明文副本，便于直接取用
    cur_dir = os.path.join(BACKUP_ROOT, "current")
    if os.path.isdir(cur_dir):
        shutil.rmtree(cur_dir, ignore_errors=True)
    os.makedirs(cur_dir, exist_ok=True)
    shutil.copy2(DB_PATH, os.path.join(cur_dir, "chemeln.db"))
    if os.path.isdir(ATTACH_DIR):
        shutil.copytree(ATTACH_DIR, os.path.join(cur_dir, "attachments"),
                        dirs_exist_ok=True)

    # 轮转：只清理本脚本生成的备份文件
    backups = sorted(
        [f for f in os.listdir(BACKUP_ROOT)
         if f.startswith("chemeln_data_") and f.endswith(".zip")],
        reverse=True)
    removed = []
    for old in backups[KEEP:]:
        try:
            os.remove(os.path.join(BACKUP_ROOT, old))
            removed.append(old)
        except OSError:
            pass

    print("备份完成")
    print(f"  文件: {out_path}")
    print(f"  大小: {size_kb:.1f} KB | 附件: {n_attach} 个")
    print(f"  明文副本: {cur_dir}")
    print(f"  备份目录: {BACKUP_ROOT}（项目外，共保留最近 {KEEP} 份）")
    if removed:
        print(f"  已清理旧备份: {len(removed)} 份")
    print()
    print("  提示: 建议再定期把该目录复制到U盘或网盘，实现真正的异地备份。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
