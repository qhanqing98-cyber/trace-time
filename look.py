"""外观设置面板：底色、强调色、透明度、圆角、毛玻璃，改完立即生效。"""

import tkinter as tk

import winfx
from theme import ACCENTS, BASES, C, F, sp
from widgets import Checkbox, RoundButton, Slider, divider, round_poly


class Swatch(tk.Canvas):
    """色块：圆角方块（底色）或圆形（强调色）。"""

    def __init__(self, master, color, label, command, active=False, shape="rect", bg=None):
        base = bg or master.cget("bg")
        self._shape = shape
        self._color = color
        self._active = active
        self._cmd = command
        self._cw, self._ch = sp(46), sp(30)
        super().__init__(master, width=self._cw, height=self._ch + sp(20), bg=base,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.label_holder = label
        self._draw()
        self.bind("<Button-1>", lambda _e: self._cmd())

    def _draw(self):
        self.delete("all")
        edge = C["accent"] if self._active else C["line"]
        top = sp(2)
        if self._shape == "circle":
            r = sp(13)
            cx, cy = self._cw / 2, top + sp(13)
            self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self._color, outline="")
            if self._active:
                self.create_oval(cx - r - sp(3), cy - r - sp(3), cx + r + sp(3), cy + r + sp(3),
                                 outline=C["accent"], width=max(2, sp(1.6)))
        else:
            round_poly(self, sp(2), top, self._cw - sp(2), top + sp(26), sp(8),
                       fill=self._color, outline=edge, width=max(1, sp(1)))
        self.create_text(self._cw / 2, self._ch + sp(8), text=self.label_holder,
                         fill=C["text"] if self._active else C["dim"], font=F["tiny"])


class LookPanel(tk.Toplevel):
    def __init__(self, master, app, look, geometry=None):
        super().__init__(master)
        self.app = app
        self.look = dict(look)
        self.withdraw()
        self.title("外观设置")
        self.configure(bg=C["card"])
        self.resizable(False, False)
        self.transient(app)
        self._cw, self._ch = sp(430), sp(700)
        self._build()
        if geometry:
            self.geometry(geometry)
        else:
            self._place_right()
        self.deiconify()
        self.after(60, self._paint_frame)

    def _paint_frame(self):
        hwnd = winfx.hwnd_of(self)
        if hwnd:
            winfx.dark_titlebar(hwnd)
            winfx.round_window(hwnd)

    def _place_right(self):
        self.update_idletasks()
        root = self.app.winfo_toplevel()
        x = root.winfo_rootx() + root.winfo_width() - self._cw - sp(40)
        y = root.winfo_rooty() + sp(90)
        if x < 0:
            x = max(0, root.winfo_rootx() + sp(80))
        self.geometry("%dx%d+%d+%d" % (self._cw, self._ch, x, y))

    # ------------------------------------------------------------------ 布局
    def _build(self):
        wrap = tk.Frame(self, bg=C["card"])
        wrap.pack(fill="both", expand=True, padx=sp(22), pady=sp(18))

        head = tk.Frame(wrap, bg=C["card"])
        head.pack(fill="x")
        tk.Label(head, text="外观", font=F["title"], bg=C["card"], fg=C["text"]).pack(side="left")
        RoundButton(head, "完成", command=self.destroy, width=84, height=32,
                    parent_bg=C["card"]).pack(side="right")

        tk.Label(wrap, text="底色", font=F["small"], bg=C["card"], fg=C["mute"],
                 anchor="w").pack(fill="x", pady=(sp(14), sp(6)))
        row = tk.Frame(wrap, bg=C["card"])
        row.pack(fill="x")
        for key, info in BASES.items():
            sw = Swatch(row, info["card"], info["label"],
                        command=lambda k=key: self.app.set_look(base=k),
                        active=(key == self.look.get("base")), bg=C["card"])
            sw.pack(side="left", padx=(0, sp(6)))

        tk.Label(wrap, text="强调色", font=F["small"], bg=C["card"], fg=C["mute"],
                 anchor="w").pack(fill="x", pady=(sp(10), sp(6)))
        row2 = tk.Frame(wrap, bg=C["card"])
        row2.pack(fill="x")
        for key, info in ACCENTS.items():
            sw = Swatch(row2, info["hex"], info["label"],
                        command=lambda k=key: self.app.set_look(accent=k),
                        active=(key == self.look.get("accent")), shape="circle", bg=C["card"])
            sw.pack(side="left", padx=(0, sp(4)))

        divider(wrap, pady=(sp(10), sp(12)))

        label_row = tk.Frame(wrap, bg=C["card"])
        label_row.pack(fill="x")
        tk.Label(label_row, text="窗口透明度", font=F["small"], bg=C["card"],
                 fg=C["mute"]).pack(side="left")
        self.alpha_lbl = tk.Label(
            label_row, text="%d%%" % round(float(self.look.get("alpha", 0.96)) * 100),
            font=F["mono"], bg=C["card"], fg=C["dim"],
        )
        self.alpha_lbl.pack(side="right")
        self.slider = Slider(wrap, value=float(self.look.get("alpha", 0.96)), lo=0.55, hi=1.0,
                             command=self._on_alpha, width=380, bg=C["card"])
        self.slider.pack(fill="x", pady=(sp(2), sp(4)))

        tk.Label(wrap, text="圆角", font=F["small"], bg=C["card"], fg=C["mute"],
                 anchor="w").pack(fill="x", pady=(sp(8), sp(6)))
        row3 = tk.Frame(wrap, bg=C["card"])
        row3.pack(fill="x")
        for radius, label in ((14, "小"), (20, "中"), (28, "大")):
            sw = Swatch(row3, C["card3"], label,
                        command=lambda r=radius: self.app.set_look(radius=r),
                        active=(radius == self.look.get("radius")), bg=C["card"])
            sw.pack(side="left", padx=(0, sp(6)))

        self.blur_var = tk.BooleanVar(value=bool(self.look.get("blur", True)))
        Checkbox(wrap, "毛玻璃模糊（窗口背景磨砂）", self.blur_var, self._on_blur,
                 bg=C["card"]).pack(anchor="w", pady=(sp(12), 0))

        tk.Label(wrap, text="透明度越低，桌面透出来越多；配毛玻璃最好看。",
                 font=F["tiny"], bg=C["card"], fg=C["mute"], anchor="w",
                 wraplength=sp(370), justify="left").pack(fill="x", pady=(sp(6), 0))

        divider(wrap, pady=(sp(12), sp(8)))
        tk.Label(wrap, text="数据文件（bat 和 exe 都用这一份）", font=F["small"],
                 bg=C["card"], fg=C["mute"], anchor="w").pack(fill="x")
        tk.Label(wrap, text=str(self.app.store.path), font=F["tiny"], bg=C["card"],
                 fg=C["dim"], anchor="w", justify="left",
                 wraplength=sp(380)).pack(fill="x", pady=(sp(2), sp(6)))
        RoundButton(wrap, "打开数据文件夹", command=self._open_folder, width=142, height=32,
                    bg=C["card3"], fg=C["dim"], parent_bg=C["card"]).pack(anchor="w")

        RoundButton(wrap, "恢复默认外观", command=self._reset, width=130, height=34,
                    bg=C["card3"], fg=C["dim"], parent_bg=C["card"]).pack(
            side="bottom", anchor="w", pady=(sp(8), 0))

    def _open_folder(self):
        import os

        try:
            folder = self.app.store.path.parent
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))
        except Exception:
            pass

    # ------------------------------------------------------------------ 事件
    def _on_alpha(self, value):
        self.alpha_lbl.configure(text="%d%%" % round(value * 100))
        self.app.set_look(alpha=round(value, 3))

    def _on_blur(self):
        self.app.set_look(blur=bool(self.blur_var.get()))

    def _reset(self):
        from theme import LOOK_DEFAULT

        self.app.set_look(**dict(LOOK_DEFAULT))
        if self.winfo_exists():
            self.destroy()

