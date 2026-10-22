# -*- coding: utf-8 -*-
"""ChemELN 自动备份 — 后台定时把数据库与附件打包备份，并按份数轮转清理。

设计要点：
- 纯标准库（threading + zipfile + sqlite3），不引入调度依赖，Windows/Linux 通用
- 每个备份产出**单个 zip**（内含 chemeln.db + attachments/），恢复时解压覆盖 data/ 即可
- 配置存 settings 表，前端「数据管理」页可改（开关 / 间隔小时 / 保留份数）
- 线程为 daemon，随服务进程退出；每 30 分钟醒一次检查是否到期
"""
import os
import sqlite3
import threading
import time
import zipfile
from datetime import datetime

from config import DB_PATH, ATTACH_DIR, BACKUP_DIR

AUTO_DIR = os.path.join(BACKUP_DIR, "auto")
LOG_PATH = os.path.join(BACKUP_DIR, "auto_backup.log")

DEFAULTS = {
    "auto_backup_enabled": "1",
    "auto_backup_interval_hours": "24",
    "auto_backup_keep": "7",
    "auto_backup_last": "",
}

_thread = None
_stop = threading.Event()


# ---------------------------------------------------------------- 配置
def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def get_settings() -> dict:
    """读取自动备份配置（缺省项自动补默认值）。"""
    cfg = dict(DEFAULTS)
    try:
        c = _conn()
        rows = c.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'auto_backup%'").fetchall()
        c.close()
        for r in rows:
            if r["value"] is not None:
                cfg[r["key"]] = r["value"]
    except Exception as e:
        _log(f"读取配置失败: {e}")
    return {
        "enabled": cfg["auto_backup_enabled"] == "1",
        "interval_hours": _int(cfg["auto_backup_interval_hours"], 24, 1, 720),
        "keep": _int(cfg["auto_backup_keep"], 7, 1, 100),
        "last_backup_at": cfg["auto_backup_last"] or "",
    }


def update_settings(enabled=None, interval_hours=None, keep=None) -> dict:
    """更新自动备份配置。"""
    pairs = []
    if enabled is not None:
        pairs.append(("auto_backup_enabled", "1" if enabled else "0"))
    if interval_hours is not None:
        pairs.append(("auto_backup_interval_hours",
                      str(_int(interval_hours, 24, 1, 720))))
    if keep is not None:
        pairs.append(("auto_backup_keep", str(_int(keep, 7, 1, 100))))
    if pairs:
        c = _conn()
        for k, v in pairs:
            c.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
        c.commit()
        c.close()
    return get_settings()


def _int(value, default, lo, hi):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _log(msg: str):
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
            f.write(line)
    except Exception:
        pass


# ---------------------------------------------------------------- 备份
def run_backup(tag: str = "auto") -> dict:
    """执行一次备份：DB + 附件 → 单个 zip。返回备份信息。"""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("数据库文件不存在")
    out_dir = AUTO_DIR if tag == "auto" else BACKUP_DIR
    os.makedirs(out_dir, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"chemeln_{tag}_{stamp}.zip"
    out_path = os.path.join(out_dir, name)

    # 数据库：用 sqlite3 backup API 生成一致快照（避免写入中复制损坏）
    # 文件名带 pid，避免同秒并发（定时线程与手动备份可能同时触发）撞名
    tmp_db = os.path.join(out_dir, f".tmp_{stamp}_{os.getpid()}.db")
    src = sqlite3.connect(DB_PATH, timeout=15)
    dst = sqlite3.connect(tmp_db)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    n_files = 0
    try:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            z.write(tmp_db, "chemeln.db")
            if os.path.isdir(ATTACH_DIR):
                for root, _dirs, files in os.walk(ATTACH_DIR):
                    for fn in files:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, ATTACH_DIR)
                        z.write(full, os.path.join("attachments", rel))
                        n_files += 1
    finally:
        _cleanup_temp(out_dir, tmp_db)

    size = os.path.getsize(out_path)
    # 记录上次备份时间
    c = _conn()
    c.execute("INSERT INTO settings (key, value) VALUES ('auto_backup_last', ?) "
              "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    c.commit()
    c.close()

    _log(f"备份完成 [{tag}] {name} ({size/1024/1024:.2f} MB, {n_files} 个附件)")
    return {"name": name, "path": out_path, "size": size,
            "attachments": n_files, "tag": tag,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def _cleanup_temp(out_dir: str, tmp_db: str = None):
    """删除本次临时快照，并顺带清理历史残留。

    Windows 上偶发句柄未释放导致删除失败。此时只记日志、不抛异常，
    否则「备份其实已成功」的结果会被误判为失败；残留文件留到下次再清。
    """
    targets = [tmp_db] if tmp_db else []
    cutoff = time.time() - 600  # 只清理 10 分钟前的遗留，避免误删并发任务的文件
    try:
        for fn in os.listdir(out_dir):
            if fn.startswith(".tmp_") and fn.endswith(".db"):
                p = os.path.join(out_dir, fn)
                try:
                    if os.path.getmtime(p) < cutoff:
                        targets.append(p)
                except OSError:
                    pass
    except OSError:
        pass
    for p in dict.fromkeys(targets):
        if not p or not os.path.exists(p):
            continue
        try:
            os.remove(p)
        except OSError as e:
            _log(f"临时文件清理失败（下次备份时重试）: {os.path.basename(p)}: {e}")


def prune_backups(keep: int = 7) -> list:
    """轮转清理自动备份，仅保留最近 keep 份。返回被删除的文件名。"""
    if not os.path.isdir(AUTO_DIR):
        return []
    items = []
    for fn in os.listdir(AUTO_DIR):
        if fn.startswith("chemeln_auto_") and fn.endswith(".zip"):
            full = os.path.join(AUTO_DIR, fn)
            items.append((os.path.getmtime(full), fn))
    items.sort(reverse=True)
    removed = []
    for _mtime, fn in items[keep:]:
        try:
            os.remove(os.path.join(AUTO_DIR, fn))
            removed.append(fn)
        except OSError as e:
            _log(f"清理失败 {fn}: {e}")
    if removed:
        _log(f"轮转清理 {len(removed)} 份旧备份（保留 {keep} 份）")
    return removed


def list_backups() -> list:
    """列出所有备份（自动 + 手动），按时间倒序。"""
    out = []
    for d, tag in ((AUTO_DIR, "auto"), (BACKUP_DIR, "manual")):
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.startswith("."):      # 跳过 .tmp_*.db 等临时文件
                continue
            full = os.path.join(d, fn)
            if not os.path.isfile(full):
                continue
            if fn.endswith(".zip"):
                out.append({"name": fn, "tag": tag, "size": os.path.getsize(full),
                            "created_at": datetime.fromtimestamp(
                                os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M:%S")})
            elif fn.endswith(".db") and tag == "manual":
                out.append({"name": fn, "tag": "manual-db", "size": os.path.getsize(full),
                            "created_at": datetime.fromtimestamp(
                                os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M:%S")})
    out.sort(key=lambda x: x["created_at"], reverse=True)
    return out


def find_backup(name: str):
    """按文件名定位备份（防目录穿越）。返回绝对路径或 None。"""
    safe = os.path.basename(name or "")
    if not safe or safe != name or safe.startswith("."):
        return None
    for d, tag in ((AUTO_DIR, "auto"), (BACKUP_DIR, "manual")):
        full = os.path.join(d, safe)
        if os.path.isfile(full):
            return full
    return None


# ---------------------------------------------------------------- 调度
def _due(cfg: dict) -> bool:
    if not cfg["last_backup_at"]:
        return True
    try:
        last = datetime.strptime(cfg["last_backup_at"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True
    return (datetime.now() - last).total_seconds() >= cfg["interval_hours"] * 3600


def _loop():
    _log("自动备份线程已启动")
    # 启动后等 90 秒再首查，避免与启动初始化抢 IO
    if _stop.wait(90):
        return
    while not _stop.is_set():
        try:
            cfg = get_settings()
            if cfg["enabled"] and _due(cfg):
                run_backup("auto")
                prune_backups(cfg["keep"])
        except Exception as e:
            _log(f"自动备份异常: {type(e).__name__}: {e}")
        if _stop.wait(1800):  # 每 30 分钟检查一次
            break


def start_scheduler():
    """启动后台备份线程（幂等）。"""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="chemeln-auto-backup", daemon=True)
    _thread.start()


def stop_scheduler():
    _stop.set()
