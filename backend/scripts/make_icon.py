# -*- coding: utf-8 -*-
"""生成合迹 ChemELN 品牌图标（网页 favicon / 侧边栏 logo / Windows 快捷方式图标）。

从一张方形母图（设计稿 / AI 生成图）出发，自动完成三件事：
  1) 裁掉四周白边 —— 取非白内容包围盒，并摆正成正方形（顺带把画在角落的
     平台水印排除掉，因为水印落在内容包围盒之外）
  2) 圆角矩形遮罩 —— 把四角做成透明，桌面快捷方式与浏览器标签页显示更干净
  3) 输出成套产物到 frontend/img/ ：
       logo.png       512×512   页面 / 侧边栏
       logo-192.png   192×192   apple-touch-icon
       logo-64.png     64×64    内嵌备用
       logo.ico       16/24/32/48/64/128/256   favicon + Windows 快捷方式

为什么固化成本脚本：母图带白边、平台水印，圆角半径与各尺寸都需要可复现，
换一张品牌图重跑一次即可，不必人工在画图软件里反复对齐像素。

用法：
    backend\\venv\\Scripts\\python backend\\scripts\\make_icon.py --probe
    backend\\venv\\Scripts\\python backend\\scripts\\make_icon.py
    backend\\venv\\Scripts\\python backend\\scripts\\make_icon.py --src 新图.png --radius-ratio 0.16
"""
import argparse
import os
import shutil
import sys

# 输出编码守卫：本脚本输出给用户控制台，保持系统编码（Windows 通常 cp936），
# 只放宽不可编码字符；强行改 UTF-8 会让 cmd 里显示成乱码。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SRC = os.path.join(ROOT, "private", "brand", "logo-source.jpg")
OUT_DIR = os.path.join(ROOT, "frontend", "img")

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
PNG_SIZES = {512: "logo.png", 192: "logo-192.png", 64: "logo-64.png"}


def log(msg: str):
    print(msg, flush=True)


def content_mask(im, sat_thresh: int = 60, dark_thresh: int = 150):
    """主体图案的二值掩码。

    ⛔ 为什么要看颜色而不是只看「是否白」：设计稿常在一角印平台水印（如
    “豆包AI生成”），水印是**浅灰细线**，落在图标之外。仅用「灰度 < 250」
    判非白，水印会被算进包围盒 —— 结果是裁出来的方框偏到右下角、还把水印
    包进图标里。图标本体（这里是一整块饱和的深蓝圆角底）与灰水印在两个
    特征上可分：
        饱和度 S 高（彩色底）  或  明度 V 低（深色/黑白稿）
    灰水印两者都不满足，被干净排除。
    """
    import numpy as np
    hsv = np.asarray(im.convert("HSV"), dtype=np.uint8)
    sat, val = hsv[:, :, 1], hsv[:, :, 2]
    return (sat > sat_thresh) | (val < dark_thresh)


def content_bbox(im, sat_thresh: int = 60, dark_thresh: int = 150, min_ratio: float = 0.0):
    """返回主体内容的包围盒 (left, top, right, bottom)。"""
    import numpy as np
    mask = content_mask(im, sat_thresh, dark_thresh)
    row_cnt = mask.sum(axis=1)
    col_cnt = mask.sum(axis=0)
    r_thr = max(1, int(round(im.height * min_ratio)))
    c_thr = max(1, int(round(im.width * min_ratio)))
    rows = np.where(row_cnt >= r_thr)[0]
    cols = np.where(col_cnt >= c_thr)[0]
    if rows.size == 0 or cols.size == 0:
        return None
    return (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)


def square_crop(im, bbox, shrink: float = 0.004):
    """以内容中心为准裁出正方形，四边都不留白。

    ⛔ 为什么用「较小边」而不是「较大边」：包围盒的高宽常差几个像素
    （这张图 1276×1260），按较大边摆正会让短边方向补出一条白边，
    缩放后仍能看到一条白线。改为按较小边 cover 裁切（多出来的长边方向
    本来就位于图案的纯色边框中，切掉无损），再统一向内缩 shrink（每边
    约 0.4%）吸收包围盒检测的 ±1px 误差。
    """
    l, t, r, b = bbox
    cx, cy = (l + r) / 2.0, (t + b) / 2.0
    side = max(8, int(round(min(r - l, b - t) * (1 - 2 * shrink))))
    half = side / 2.0
    box = (int(round(cx - half)), int(round(cy - half)),
           int(round(cx - half)) + side, int(round(cy - half)) + side)
    box = (max(0, box[0]), max(0, box[1]),
           min(im.width, box[2]), min(im.height, box[3]))
    return im.crop(box)


def round_mask(size: int, radius_ratio: float, supersample: int = 4):
    """抗锯齿的圆角矩形遮罩（4 倍超采样后缩回来）。"""
    from PIL import Image, ImageDraw
    big = size * supersample
    r = max(1, int(round(big * radius_ratio)))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=r, fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def probe(im, sat_thresh: int = 60, dark_thresh: int = 150):
    """体检母图：白边、内容尺寸、圆角半径估计、水印位置。"""
    import numpy as np
    log(f"母图尺寸: {im.width} x {im.height}  ({im.mode})")
    bbox = content_bbox(im, sat_thresh, dark_thresh)
    if not bbox:
        log("错误: 未检测到主体图案")
        return
    l, t, r, b = bbox
    log(f"内容包围盒: left={l} top={t} right={r} bottom={b}"
        f"  →  {r - l} x {b - t}")
    log(f"白边: 左{l} 上{t} 右{im.width - r} 下{im.height - b}")

    mask = content_mask(im, sat_thresh, dark_thresh)
    # 圆角半径估计：在左上角区域内，逐行找第一个主体像素的 x
    log("左上角轮廓采样（行 → 首个图案像素 x，用于估计圆角半径）:")
    for dy in (0, 2, 5, 10, 20, 40, 60, 90, 120, 160, 200):
        y = t + dy
        if y >= im.height:
            break
        row = np.where(mask[y, l:r])[0]
        inset = int(row[0]) if row.size else -1
        log(f"   y=+{dy:<4d} x0=+{inset}")

    # 水印检测：主体包围盒之外是否还有其它内容（水印/署名）
    outside = mask.copy()
    outside[t:b, l:r] = False
    n = int(outside.sum())
    log(f"包围盒外残留像素: {n}"
        f"（{'>0 说明框外还有水印或署名，已被排除' if n else '干净'}）")


def build(src: str, radius_ratio: float, sat_thresh: int, dark_thresh: int, out_dir: str):
    from PIL import Image
    im = Image.open(src)
    im = im.convert("RGB")
    log(f"读取母图: {src}  {im.width}x{im.height}")

    bbox = content_bbox(im, sat_thresh, dark_thresh)
    if not bbox:
        raise SystemExit("错误: 未能检测到图案内容（是否整张都是白色？）")
    square = square_crop(im, bbox)
    log(f"裁白边并摆正: {square.width}x{square.height}")

    # 先缩到 512 母版（做圆角遮罩也在这个尺寸上，保证各尺寸一致）
    master = square.resize((512, 512), Image.Resampling.LANCZOS)
    mask = round_mask(512, radius_ratio)
    master.putalpha(mask)

    os.makedirs(out_dir, exist_ok=True)
    written = []

    for size, name in PNG_SIZES.items():
        img = master if size == 512 else master.resize((size, size), Image.Resampling.LANCZOS)
        path = os.path.join(out_dir, name)
        img.save(path, format="PNG", optimize=True)
        written.append((path, os.path.getsize(path)))

    ico_path = os.path.join(out_dir, "logo.ico")
    master.save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    written.append((ico_path, os.path.getsize(ico_path)))

    log("")
    for path, size in written:
        log(f"  已生成 {os.path.relpath(path, ROOT)}  ({size:,} B)")
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC, help="母图路径")
    ap.add_argument("--out-dir", default=OUT_DIR, help="输出目录")
    ap.add_argument("--radius-ratio", type=float, default=0.16,
                    help="圆角半径占边长比例（默认 0.16；须略大于母图自身圆角，"
                         "否则遮罩会切进圆角外的白底而露出白角）")
    ap.add_argument("--sat-thresh", type=int, default=60,
                    help="饱和度阈值：高于它视为彩色图案（默认 60）")
    ap.add_argument("--dark-thresh", type=int, default=150,
                    help="明度阈值：低于它视为深色图案（默认 150）")
    ap.add_argument("--probe", action="store_true", help="只体检母图，不生成")
    args = ap.parse_args()

    if not os.path.exists(args.src):
        log(f"错误: 找不到母图 {args.src}")
        log("提示: 用 --src 指定图片路径；或把母图放到 private/brand/logo-source.jpg")
        return 1

    if args.probe:
        from PIL import Image
        probe(Image.open(args.src), args.sat_thresh, args.dark_thresh)
        return 0

    try:
        build(args.src, args.radius_ratio, args.sat_thresh,
              args.dark_thresh, args.out_dir)
    except SystemExit:
        raise
    except Exception as e:
        log(f"错误: {type(e).__name__}: {e}")
        return 1
    log("")
    log("完成。下一步：")
    log("  1) 页面已引用 /static/img/logo.png 与 /static/img/logo.ico，刷新浏览器即可")
    log("  2) 重新运行 install.bat（或 setup_shortcuts.vbs install）刷新桌面快捷方式图标")
    return 0


if __name__ == "__main__":
    sys.exit(main())
