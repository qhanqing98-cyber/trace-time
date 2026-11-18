"""Windows 窗口材质：深色标题栏、圆角窗口、毛玻璃（模糊）背景。

全部用 ctypes 直接调 DWM / user32，失败就安静降级，不影响程序运行。
"""

import ctypes

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_WINDOW_BORDER_COLOR = 34

WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3


class ACCENTPOLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def hwnd_of(widget):
    """拿到 Tk 顶层窗口真正的 HWND。"""
    try:
        return int(ctypes.windll.user32.GetAncestor(int(widget.winfo_id()), 2))
    except Exception:
        return 0


def dark_titlebar(hwnd, on=True):
    try:
        value = ctypes.c_int(1 if on else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
        return True
    except Exception:
        return False


def round_window(hwnd, pref=DWMWCP_ROUND):
    try:
        value = ctypes.c_int(pref)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(value), ctypes.sizeof(value)
        )
        return True
    except Exception:
        return False


def _accent(hwnd, state, gradient=0):
    try:
        policy = ACCENTPOLICY(state, 0, gradient, 0)
        data = WINDOWCOMPOSITIONATTRIBDATA(
            WCA_ACCENT_POLICY,
            ctypes.cast(ctypes.byref(policy), ctypes.c_void_p),
            ctypes.sizeof(policy),
        )
        fn = ctypes.windll.user32.SetWindowCompositionAttribute
        fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        return bool(fn(ctypes.c_void_p(hwnd), ctypes.byref(data)))
    except Exception:
        return False


def blur(hwnd, rgb="#101116", strength=0x8c):
    """毛玻璃：GradientColor 是 0xAABBGGRR，A 越大玻璃越浓。"""
    try:
        rgb = rgb.lstrip("#")
        r, g, b = int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)
        gradient = ((strength & 0xFF) << 24) | (b << 16) | (g << 8) | r
        return _accent(hwnd, ACCENT_ENABLE_BLURBEHIND, gradient)
    except Exception:
        return False


def clear_blur(hwnd):
    return _accent(hwnd, ACCENT_DISABLED, 0)


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
SWP_FLAGS = 0x0002 | 0x0001 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED


def unlayer(widget):
    """把 WS_EX_LAYERED 去掉。

    Tk 的 -alpha 一旦设过小于 1 的值，窗口就永久带上了 WS_EX_LAYERED；
    以后就算把 -alpha 设回 1.0，分层标记也还在——那意味着文字一直用不了
    ClearType、每帧都多一层合成。所以「不透明」这一档必须手动摘掉它。
    """
    hwnd = widget if isinstance(widget, int) else hwnd_of(widget)
    if not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
        if not style & WS_EX_LAYERED:
            return True
        user32.SetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE, style & ~WS_EX_LAYERED)
        user32.SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, 0, 0, SWP_FLAGS)
        return True
    except Exception:
        return False


def set_layered(widget, alpha):
    """自己把分层标记装回去并设不透明度（0~1）。

    摘过一次 WS_EX_LAYERED 之后，Tk 再把 -alpha 设成小于 1 也不会重新分层，
    滑杆就会「怎么拖都没变化」。所以这里两边都对齐一下。
    """
    hwnd = widget if isinstance(widget, int) else hwnd_of(widget)
    if not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
        if not style & WS_EX_LAYERED:
            user32.SetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE, style | WS_EX_LAYERED)
            user32.SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, 0, 0, SWP_FLAGS)
        level = max(0, min(255, int(round(float(alpha) * 255))))
        return bool(user32.SetLayeredWindowAttributes(ctypes.c_void_p(hwnd), 0, level, 0x00000002))
    except Exception:
        return False
