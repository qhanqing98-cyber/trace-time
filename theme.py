"""配色、字体、DPI 缩放：所有视觉令牌都在这里。

关键点：进程先声明 DPI 感知（否则 Windows 会把整个窗口按 150% 位图拉伸，
文字必然发糊），然后所有尺寸都乘上 SCALE，字体用「像素大小」而不是「点」，
这样字高落在整数像素上，配合 ClearType 就是清晰的。
"""

import ctypes
import tkinter as tk
from tkinter import ttk

DESIGN_DPI = 96
UI = "Microsoft YaHei UI"
MONO = "Consolas"


def _enable_dpi_awareness():
    """Per-Monitor V2 → 交给系统别替我们缩放。"""
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_enable_dpi_awareness()


def _system_dpi():
    try:
        value = int(ctypes.windll.user32.GetDpiForSystem())
        if 48 <= value <= 600:
            return value
    except Exception:
        pass
    return DESIGN_DPI


SCALE = _system_dpi() / float(DESIGN_DPI)


def sp(value):
    """设计像素 → 当前 DPI 下的物理像素。"""
    return int(round(value * SCALE))


# ----------------------------------------------------------------- 颜色工具
def _clamp(v):
    return max(0, min(255, int(round(v))))


def hex2rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(r, g, b):
    return "#%02x%02x%02x" % (_clamp(r), _clamp(g), _clamp(b))


def mix(c1, c2, t):
    a, b = hex2rgb(c1), hex2rgb(c2)
    return rgb2hex(*[a[i] + (b[i] - a[i]) * t for i in range(3)])


def shade(color, factor):
    r, g, b = hex2rgb(color)
    if factor >= 1:
        k = factor - 1
        return rgb2hex(r + (255 - r) * k, g + (255 - g) * k, b + (255 - b) * k)
    return rgb2hex(r * factor, g * factor, b * factor)


# ------------------------------------------------------------------- 底色
BASES = {
    "night": {"bg": "#080b11", "sidebar": "#0c1017", "card": "#141924", "label": "深夜"},
    "graphite": {"bg": "#0e0f11", "sidebar": "#131417", "card": "#1c1e22", "label": "石墨"},
    "plum": {"bg": "#0c0913", "sidebar": "#130f1e", "card": "#1d1730", "label": "暗紫"},
    "ocean": {"bg": "#061019", "sidebar": "#0a1620", "card": "#0f2430", "label": "深海"},
}

ACCENTS = {
    "blue": {"hex": "#5b8cff", "label": "星蓝"},
    "violet": {"hex": "#a78bfa", "label": "鸢尾"},
    "cyan": {"hex": "#38d6d6", "label": "青瓷"},
    "mint": {"hex": "#3ecf8e", "label": "薄荷"},
    "amber": {"hex": "#ffb86b", "label": "琥珀"},
    "rose": {"hex": "#ff7a9c", "label": "玫瑰"},
}

LOOK_DEFAULT = {
    "base": "night",
    "accent": "blue",
    "alpha": 0.96,
    "blur": True,
    "radius": 20,
}

C = {}
F = {}


def build_palette(base="night", accent="blue", radius=20):
    b = BASES.get(base, BASES["night"])
    acc = ACCENTS.get(accent, ACCENTS["blue"])["hex"]
    card = b["card"]
    palette = {
        "base": base if base in BASES else "night",
        "accent_key": accent if accent in ACCENTS else "blue",
        "bg": b["bg"],
        "sidebar": b["sidebar"],
        "card": card,
        "card2": mix(card, "#ffffff", 0.055),
        "card3": mix(card, "#ffffff", 0.10),
        "line": mix(card, "#ffffff", 0.085),
        "edge": mix(card, "#ffffff", 0.16),
        "sheen": mix(card, "#ffffff", 0.09),
        "text": "#eef2f9",
        "white": "#ffffff",
        "accent": acc,
        "accent_dim": mix(acc, card, 0.35),
        "accent_soft": mix(card, acc, 0.20),
        "blue": acc,
        "glass_hover": mix(b["sidebar"], "#ffffff", 0.045),
        "green": "#3ecf8e",
        "orange": "#ffb86b",
        "red": "#ff7189",
        "purple": "#b18bfa",
        "yellow": "#f5d67c",
        "radius": sp(radius),
        "radius_sm": sp(11),
    }
    palette["dim"] = mix(palette["text"], card, 0.42)
    palette["mute"] = mix(palette["text"], card, 0.65)
    return palette


def build_fonts():
    def f(size, weight="normal", family=UI):
        return (family, -max(9, int(round(size * SCALE))), weight)

    return {
        "title": f(20, "bold"),
        "h1": f(16, "bold"),
        "h2": f(14, "bold"),
        "body": f(14),
        "body_strike": f(14, "overstrike"),
        "small": f(13),
        "small_strike": f(13, "overstrike"),
        "tiny": f(12),
        "btn": f(14, "bold"),
        "btn_lg": f(15, "bold"),
        "mono": f(13, "normal", MONO),
        "mono_sm": f(12, "normal", MONO),
        "mono_md": f(15, "normal", MONO),
        "num": f(22, "bold", MONO),
        "big": f(62, "bold", MONO),
        "pomo": f(46, "bold", MONO),
        "glyph": f(13, "normal", MONO),
    }


def rebuild(look=None, base=None, accent=None, radius=None):
    """重新生成全部视觉令牌（改配色时调用，随后重建视图）。

    既可以传一个 look 字典，也可以分开传 base / accent / radius。
    """
    if isinstance(look, dict):
        base = look.get("base")
        accent = look.get("accent")
        radius = look.get("radius")
    base = base if base in BASES else "night"
    accent = accent if accent in ACCENTS else "blue"
    try:
        radius = max(8, int(radius if radius is not None else LOOK_DEFAULT["radius"]))
    except (TypeError, ValueError):
        radius = LOOK_DEFAULT["radius"]
    C.clear()
    C.update(build_palette(base, accent, radius))
    F.clear()
    F.update(build_fonts())


C.update(build_palette())
F.update(build_fonts())


def style_ttk(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(
        "Vertical.TScrollbar",
        background=mix(C["card"], "#ffffff", 0.18),
        troughcolor=C["card"],
        bordercolor=C["card"],
        arrowcolor=C["dim"],
        darkcolor=mix(C["card"], "#ffffff", 0.18),
        lightcolor=mix(C["card"], "#ffffff", 0.18),
        relief="flat",
        arrowsize=sp(10),
        width=sp(9),
    )
    st.map("Vertical.TScrollbar", background=[("active", mix(C["card"], "#ffffff", 0.3))])
