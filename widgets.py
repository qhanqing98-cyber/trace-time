"""自定义控件：圆角玻璃面板、圆角按钮、圆角胶囊、圆角勾选圈、滚动容器、滑块。

Tk 原生控件没有圆角也没有半透明，所以这类"材质感"全部用 Canvas 画出来：
面板用平滑多边形画圆角 + 一道高亮描边模拟玻璃边缘，按钮/胶囊同理。
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from theme import C, F, UI, MONO, mix, shade, sp

_FONT_CACHE = {}


def font_of(spec):
    """把 F 里的字体元组变成可测量的 Font 对象（带缓存）。"""
    if isinstance(spec, tkfont.Font):
        return spec
    key = tuple(spec)
    fnt = _FONT_CACHE.get(key)
    if fnt is None:
        family, size = spec[0], spec[1]
        weight = spec[2] if len(spec) > 2 else "normal"
        overstrike = spec[3] if len(spec) > 3 else 0
        fnt = tkfont.Font(family=family, size=size, weight=weight, overstrike=overstrike)
        _FONT_CACHE[key] = fnt
    return fnt


def round_poly(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, splinesteps=32, **kw)


class Glass(tk.Canvas):
    """圆角玻璃面板；内容放进 self.body。"""

    def __init__(self, master, padx=22, pady=18, radius=None, fill=None, edge=None,
                 sheen=True, bg=None, **kw):
        parent_bg = bg or master.cget("bg")
        super().__init__(master, bg=parent_bg, highlightthickness=0, bd=0, **kw)
        self.fill = fill or C["card"]
        self._edge = edge or C["edge"]
        self._padx, self._pady = sp(padx), sp(pady)
        want = C["radius"] if radius is None else sp(radius)
        self._radius = max(sp(6), min(want, self._padx, self._pady))
        self._sheen = sheen
        self._req = (0, 0)
        self.body = tk.Frame(self, bg=self.fill)
        self.body.place(x=self._padx, y=self._pady)
        self.bind("<Configure>", self._on_configure)
        self.body.bind("<Configure>", self._sync_request)

    # ------------------------------------------------------------ 尺寸协商
    def _sync_request(self, _=None):
        """让面板的自然尺寸跟着内容走（pack/grid 自适应时用）。"""
        w = self.body.winfo_reqwidth() + 2 * self._padx
        h = self.body.winfo_reqheight() + 2 * self._pady
        if (w, h) != self._req:
            self._req = (w, h)
            self.configure(width=w, height=h)

    def _on_configure(self, event=None):
        w, h = self.winfo_width(), self.winfo_height()
        self._paint(w, h)
        self.body.place(
            x=self._padx, y=self._pady,
            width=max(1, w - 2 * self._padx), height=max(1, h - 2 * self._pady),
        )

    def _paint(self, w, h):
        self.delete("shape")
        if w < 4 or h < 4:
            return
        r = self._radius
        round_poly(self, 0.5, 0.5, w - 0.5, h - 0.5, r, fill=self.fill, outline=self._edge, tags="shape")
        if self._sheen and h > r * 2:
            # 顶部一道很淡的高光，模拟玻璃受光
            self.create_line(
                r * 0.9, 1.5, w - r * 0.9, 1.5,
                fill=mix(self.fill, "#ffffff", 0.14), width=1, tags="shape",
            )

    def recolor(self, fill=None, edge=None, body_bg=None):
        if fill:
            self.fill = fill
        if edge:
            self._edge = edge
        if body_bg:
            self.body.configure(bg=body_bg)
        self._paint(self.winfo_width(), self.winfo_height())


class Plate(Glass):
    """卡片内部的次级圆角块（时间线条目、统计条等）。"""

    def __init__(self, master, padx=12, pady=8, fill=None, **kw):
        super().__init__(master, padx=padx, pady=pady, radius=C["radius_sm"],
                         fill=fill or C["card2"], edge=mix(C["card2"], "#ffffff", 0.06), **kw)


class RoundButton(tk.Canvas):
    def __init__(self, master, text="", command=None, width=150, height=44,
                 bg=None, fg=None, parent_bg=None, radius=None, font=None, hover=None):
        pbg = parent_bg or master.cget("bg")
        self._cw, self._ch = sp(width), sp(height)
        super().__init__(master, width=self._cw, height=self._ch, bg=pbg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._cmd = command
        self._bg = bg or C["accent"]
        self._fg = fg or "#ffffff"
        self._hover = hover or shade(self._bg, 1.18)
        self._r = radius if radius is not None else sp(12)
        self._enabled = True
        self._poly = round_poly(self, 1, 1, self._cw - 1, self._ch - 1, self._r, fill=self._bg)
        self._text = self.create_text(self._cw / 2, self._ch / 2 + 1, text=text,
                                      fill=self._fg, font=font or F["btn"])
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_text(self, text):
        self.itemconfig(self._text, text=text)

    def set_colors(self, bg=None, fg=None, hover=None):
        if bg:
            self._bg = bg
            self._hover = hover or shade(bg, 1.18)
        if fg:
            self._fg = fg
        self._repaint()

    def set_enabled(self, on):
        self._enabled = bool(on)
        self.configure(cursor="hand2" if on else "arrow")
        self._repaint()

    def _repaint(self, fill=None):
        base = fill or (self._bg if self._enabled else mix(self._bg, C["card"], 0.76))
        fg = self._fg if self._enabled else mix(self._fg, C["card"], 0.55)
        self.itemconfig(self._poly, fill=base)
        self.itemconfig(self._text, fill=fg)

    def _on_enter(self, _=None):
        if self._enabled:
            self._repaint(self._hover)

    def _on_leave(self, _=None):
        self._repaint()

    def _on_press(self, _=None):
        if self._enabled:
            self._repaint(shade(self._bg, 0.86))

    def _on_release(self, event=None):
        if not self._enabled:
            return
        self._repaint(self._hover)
        inside = event is None or (0 <= event.x <= self._cw and 0 <= event.y <= self._ch)
        if inside and self._cmd:
            self._cmd()


class Pill(tk.Canvas):
    """圆角小标签。用 .set(text=..., color=...) 更新。"""

    def __init__(self, master, text="", color=None, bg=None, font=None, padx=10, pady=3):
        base = bg or master.cget("bg")
        self._font = font or F["tiny"]
        self._color = color or C["accent"]
        self._pbg = base
        self._padx, self._pady = sp(padx), sp(pady)
        self.text = text
        w, h = self._measure()
        super().__init__(master, width=w, height=h, bg=base, highlightthickness=0, bd=0)
        self._draw()

    def _measure(self):
        fnt = font_of(self._font)
        size = self._pady + sp(1)
        w = fnt.measure(self.text) + 2 * self._padx
        h = fnt.metrics("linespace") + 2 * size
        return max(sp(18), w), max(sp(16), h)

    def _draw(self):
        self.delete("all")
        w, h = int(self.cget("width")), int(self.cget("height"))
        round_poly(self, 1, 1, w - 1, h - 1, min(w, h) / 2.0,
                   fill=mix(self._pbg, self._color, 0.18), outline=mix(self._pbg, self._color, 0.34))
        self.create_text(w / 2, h / 2 + 1, text=self.text, fill=self._color, font=self._font)

    def set(self, text=None, color=None, bg=None):
        changed = False
        if text is not None and text != self.text:
            self.text = text
            w, h = self._measure()
            self.configure(width=w, height=h)
            changed = True
        if color is not None:
            self._color = color
            changed = True
        if bg is not None:
            self._pbg = bg
            self.configure(bg=bg)
            changed = True
        if changed:
            self._draw()


class Chip(tk.Canvas):
    """可点击的圆角选择块（筛选、标签选择）。用 .set_active() 切换选中态。"""

    def __init__(self, master, text, command=None, active=False, parent_bg=None,
                 color=None, font=None, padx=12, pady=5):
        base = parent_bg or master.cget("bg")
        self._font = font or F["small"]
        self._color = color or C["accent"]
        self._pbg = base
        self._active = bool(active)
        self._cmd = command
        self.text = text
        self._padx, self._pady = sp(padx), sp(pady)
        fnt = font_of(self._font)
        w = fnt.measure(text) + 2 * self._padx
        h = fnt.metrics("linespace") + 2 * self._pady
        super().__init__(master, width=w, height=h, bg=base, highlightthickness=0, bd=0, cursor="hand2")
        self._draw()
        self.bind("<Button-1>", self._on_click)

    def _draw(self):
        self.delete("all")
        w = int(self.cget("width"))
        h = int(self.cget("height"))
        fill = mix(self._pbg, self._color, 0.22 if self._active else 0.06)
        edge = mix(self._pbg, self._color, 0.40 if self._active else 0.12)
        round_poly(self, 1, 1, w - 1, h - 1, h / 2.0, fill=fill, outline=edge)
        self.create_text(w / 2, h / 2 + 1, text=self.text,
                         fill=self._color if self._active else C["dim"], font=self._font)

    def set_active(self, active):
        self._active = bool(active)
        self._draw()

    def _on_click(self, _=None):
        if self._cmd:
            self._cmd(self)


class CheckCircle(tk.Canvas):
    def __init__(self, master, checked=False, size=22, bg=None, color=None, command=None):
        base = bg or master.cget("bg")
        self._size = sp(size)
        super().__init__(master, width=self._size, height=self._size, bg=base,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._color = color or C["green"]
        self.checked = bool(checked)
        self._cmd = command
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self._size
        w = max(2, sp(1.6))
        if self.checked:
            self.create_oval(w, w, s - w, s - w, fill=self._color, outline="")
            self.create_line(s * 0.28, s * 0.52, s * 0.44, s * 0.68, s * 0.72, s * 0.33,
                             fill=C["white"], width=max(2, sp(1.8)), capstyle="round", joinstyle="round")
        else:
            self.create_oval(w, w, s - w, s - w, outline=mix(C["card"], "#ffffff", 0.28), width=w)

    def set(self, checked):
        self.checked = bool(checked)
        self._draw()

    def _on_click(self, _=None):
        if self._cmd:
            self._cmd()


class ScrollFrame(tk.Frame):
    def __init__(self, master, bg=None, **kw):
        color = bg or C["card"]
        super().__init__(master, bg=color, **kw)
        self.canvas = tk.Canvas(self, width=1, bg=color, highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                  style="Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=color)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)
        self.inner.bind("<Enter>", self._bind_wheel)
        self.inner.bind("<Leave>", self._unbind_wheel)

    def _on_inner(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._win, width=event.width)

    def _bind_wheel(self, _=None):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        first, last = self.canvas.yview()
        if first <= 0.0 and last >= 1.0:
            return
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()


class Dropdown(tk.Menubutton):
    """扁平下拉选择（width 是字符宽度，不是像素）。"""

    def __init__(self, master, values, value=None, command=None, width=None, font=None, pad_chars=1):
        self._values = list(values)
        self.value = value if value is not None else (self._values[0] if self._values else "")
        super().__init__(
            master, text=self.value, font=font or F["body"],
            bg=C["card2"], fg=C["text"], activebackground=C["line"], activeforeground=C["text"],
            bd=0, relief="flat", highlightthickness=1,
            highlightbackground=mix(C["card2"], "#ffffff", 0.08), highlightcolor=C["accent"],
            anchor="w", padx=sp(12), pady=sp(5), cursor="hand2",
        )
        if width:
            self.configure(width=width)
        self._cmd = command
        self._menu = tk.Menu(
            self, tearoff=0, bg=C["card2"], fg=C["text"],
            activebackground=C["accent"], activeforeground="#ffffff",
            bd=0, relief="flat", font=font or F["body"],
        )
        self._rebuild()
        self.configure(menu=self._menu)

    def _rebuild(self):
        self._menu.delete(0, "end")
        for val in self._values:
            self._menu.add_command(label=val, command=lambda v=val: self.set(v, notify=True))

    def set(self, value, notify=False):
        self.value = value
        self.configure(text=value)
        if notify and self._cmd:
            self._cmd(value)

    def set_values(self, values):
        self._values = list(values)
        self._rebuild()


class Checkbox(tk.Frame):
    """圆形勾选 + 文字，整行可点。"""

    def __init__(self, master, text, variable, command=None, bg=None):
        base = bg or master.cget("bg")
        super().__init__(master, bg=base, cursor="hand2")
        self.var = variable
        self._cmd = command
        self.dot = CheckCircle(self, checked=bool(variable.get()), size=20, bg=base,
                               color=C["accent"], command=self._toggle)
        self.dot.pack(side="left")
        self.lbl = tk.Label(self, text=text, font=F["small"], bg=base, fg=C["dim"])
        self.lbl.pack(side="left", padx=sp(8))
        for widget in (self, self.lbl):
            widget.bind("<Button-1>", lambda _e: self._toggle())

    def _toggle(self):
        self.var.set(not bool(self.var.get()))
        self.dot.set(bool(self.var.get()))
        if self._cmd:
            self._cmd()


class Slider(tk.Canvas):
    """细长的滑块，用来调透明度之类。"""

    def __init__(self, master, value=0.9, lo=0.6, hi=1.0, command=None, width=240, bg=None):
        base = bg or master.cget("bg")
        self._cw, self._ch = sp(width), sp(28)
        super().__init__(master, width=self._cw, height=self._ch, bg=base,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.lo, self.hi = lo, hi
        self.value = max(lo, min(hi, value))
        self._cmd = command
        self._pad = sp(10)
        self.bind("<Button-1>", self._on_move)
        self.bind("<B1-Motion>", self._on_move)
        self._draw()

    def _draw(self):
        self.delete("all")
        y = self._ch / 2
        x1, x2 = self._pad, self._cw - self._pad
        track_h = sp(6)
        round_poly(self, x1, y - track_h / 2, x2, y + track_h / 2, track_h / 2,
                   fill=mix(C["card2"], "#ffffff", 0.10), outline="")
        ratio = (self.value - self.lo) / float(self.hi - self.lo) if self.hi > self.lo else 1
        knob_x = x1 + (x2 - x1) * ratio
        if knob_x - x1 > track_h / 2:
            round_poly(self, x1, y - track_h / 2, knob_x, y + track_h / 2, track_h / 2,
                       fill=C["accent"], outline="")
        r = sp(8)
        self.create_oval(knob_x - r, y - r, knob_x + r, y + r, fill="#ffffff", outline="")
        self.create_text(self._cw / 2, self._ch - sp(6), text="%d%%" % round(self.value * 100),
                         fill=C["dim"], font=F["tiny"])

    def _on_move(self, event):
        x1, x2 = self._pad, self._cw - self._pad
        ratio = min(1.0, max(0.0, (event.x - x1) / float(x2 - x1)))
        self.value = self.lo + (self.hi - self.lo) * ratio
        self._draw()
        if self._cmd:
            self._cmd(self.value)

    def set_value(self, value):
        self.value = max(self.lo, min(self.hi, value))
        self._draw()


def make_entry(master, width=20, font=None, textvariable=None, bg=None):
    """width 是字符宽度。"""
    return tk.Entry(
        master, width=width, font=font or F["body"],
        bg=bg or C["card2"], fg=C["text"], insertbackground=C["text"],
        disabledbackground=bg or C["card2"], disabledforeground=C["mute"],
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground=mix(C["card2"], "#ffffff", 0.08), highlightcolor=C["accent"],
    )


def divider(master, color=None, pady=0):
    line = tk.Frame(master, height=max(1, sp(1)), bg=color or C["line"])
    line.pack(fill="x", pady=pady)
    return line

