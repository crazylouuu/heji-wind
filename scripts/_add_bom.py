"""给 PowerShell 脚本加 UTF-8 BOM。

为什么需要：Windows PowerShell 5.1 读取**无 BOM** 的 UTF-8 文件时，
会按系统 ANSI 代码页（GBK）解码 → 中文乱码 → 解析器报一堆
「字符串缺少终止符」的假错误。

处理办法二选一：
  a) 给 .ps1 加 UTF-8 BOM（本脚本做的，保留中文界面）
  b) 脚本里全用 ASCII（英文界面）

用法：python scripts/_add_bom.py build\verify_release.ps1 build\build.ps1
"""
import io
import sys

BOM = b"\xef\xbb\xbf"


def add_bom(path: str) -> bool:
    with open(path, "rb") as f:
        raw = f.read()
    changed = False
    if not raw.startswith(BOM):
        with open(path, "wb") as f:
            f.write(BOM + raw)
        changed = True
    return changed


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/_add_bom.py <file.ps1> [...]")
        return 1
    for p in sys.argv[1:]:
        try:
            changed = add_bom(p)
            print(("已加 BOM: " if changed else "已有 BOM: ") + p)
        except OSError as e:
            print(f"失败 {p}: {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
