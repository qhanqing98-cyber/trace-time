"""弹窗：记录「这段时间做了什么」、文本输入、多选确认、待办编辑。"""

import tkinter as tk

from store import PRIORITY_LABEL, PRIORITIES, fmt_span
from theme import C, F, sp
from widgets import Chip, Dropdown, Glass, RoundButton, divider, make_entry
import winfx


class Modal(tk.Toplevel):
    """居中的模态窗（深色标题栏 + 圆角）。"""

    def __init__(self, parent, title="", width=560, height=400):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=C["card"])
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.result = None
        self._dw, self._dh = sp(width), sp(height)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(30, self._paint_frame)

    def _paint_frame(self):
        hwnd = winfx.hwnd_of(self)
        if hwnd:
            winfx.dark_titlebar(hwnd)
            winfx.round_window(hwnd)

    def _place(self):
        self.update_idletasks()
        root = self.master.winfo_toplevel()
        x = root.winfo_rootx() + max(0, (root.winfo_width() - self._dw) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - self._dh) // 3)
        self.geometry("%dx%d+%d+%d" % (self._dw, self._dh, x, y))

    def show(self):
        self._place()
        self.deiconify()
        self.grab_set()
        self.focus_force()
        self.wait_window()
        return self.result

    def _cancel(self):
        self.result = None
        self.destroy()


class NoteDialog(Modal):
    """暂停 / 番茄结束时，记录这一段到底做了什么。"""

    def __init__(self, parent, start, end, seconds, tags=(), recent=(), source="计时器"):
        super().__init__(parent, "记录这一段时间", width=580, height=470)
        self.seconds = seconds
        self.tag = ""
        self._tag_chips = []
        self._ph_active = False
        self._placeholder = "例如：修复登录接口报错 / 梳理需求文档 / 和同事对齐排期…"

        wrap = tk.Frame(self, bg=C["card"])
        wrap.pack(fill="both", expand=True, padx=sp(24), pady=sp(20))

        tk.Label(wrap, text="这 %s，你做了什么？" % fmt_span(seconds),
                 font=F["title"], bg=C["card"], fg=C["text"], anchor="w").pack(fill="x")
        tk.Label(wrap, text="%s – %s · %s" % (start.strftime("%H:%M"), end.strftime("%H:%M"), source),
                 font=F["small"], bg=C["card"], fg=C["dim"], anchor="w").pack(fill="x", pady=(sp(4), sp(12)))

        box = Glass(wrap, padx=12, pady=10, fill=C["card2"], radius=C["radius_sm"])
        box.pack(fill="both", expand=True)
        self.text = tk.Text(
            box.body, width=1, height=4, font=F["body"], bg=C["card2"], fg=C["text"],
            insertbackground=C["text"], bd=0, relief="flat", wrap="word",
            padx=sp(2), pady=sp(2),
        )
        self.text.pack(fill="both", expand=True)
        self._set_placeholder()
        self.text.bind("<FocusIn>", self._on_focus_in)
        self.text.bind("<FocusOut>", self._on_focus_out)

        if tags:
            tk.Label(wrap, text="归类", font=F["small"], bg=C["card"], fg=C["mute"],
                     anchor="w").pack(fill="x", pady=(sp(12), sp(6)))
            row = tk.Frame(wrap, bg=C["card"])
            row.pack(fill="x")
            for tag in tags:
                chip = Chip(row, tag, command=self._pick_tag, parent_bg=C["card"], color=C["purple"])
                chip.pack(side="left", padx=(0, sp(6)))
                self._tag_chips.append(chip)

        if recent:
            tk.Label(wrap, text="最近用过", font=F["small"], bg=C["card"], fg=C["mute"],
                     anchor="w").pack(fill="x", pady=(sp(10), sp(6)))
            row2 = tk.Frame(wrap, bg=C["card"])
            row2.pack(fill="x")
            for note in recent[:3]:
                short = note if len(note) <= 14 else note[:13] + "…"
                Chip(row2, short, command=lambda n=note: self._use_recent(n),
                     parent_bg=C["card"], color=C["dim"]).pack(side="left", padx=(0, sp(6)))

        divider(wrap, pady=(sp(14), sp(12)))

        btns = tk.Frame(wrap, bg=C["card"])
        btns.pack(fill="x")
        RoundButton(btns, "保存记录", command=self._save, width=132, height=42,
                    parent_bg=C["card"]).pack(side="left")
        RoundButton(btns, "跳过这段", command=self._cancel, width=110, height=42,
                    bg=C["card3"], fg=C["dim"], parent_bg=C["card"]).pack(side="left", padx=sp(8))
        tk.Label(btns, text="Ctrl+Enter 保存 · Esc 跳过", font=F["tiny"],
                 bg=C["card"], fg=C["mute"]).pack(side="right")

        self.bind("<Control-Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self._cancel())
        self.after(80, self.text.focus_set)

    # ------------------------------------------------------------------ 占位符
    def _set_placeholder(self):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self._placeholder)
        self.text.configure(fg=C["mute"])
        self._ph_active = True

    def _on_focus_in(self, _=None):
        if self._ph_active:
            self.text.delete("1.0", "end")
            self.text.configure(fg=C["text"])
            self._ph_active = False

    def _on_focus_out(self, _=None):
        if not self.text.get("1.0", "end").strip():
            self._set_placeholder()

    # ------------------------------------------------------------------ 交互
    def _pick_tag(self, chip):
        if self.tag == chip.text:
            self.tag = ""
            chip.set_active(False)
            return
        self.tag = chip.text
        for c in self._tag_chips:
            c.set_active(c is chip)

    def _use_recent(self, note):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", note)
        self.text.configure(fg=C["text"])
        self._ph_active = False
        self.text.focus_set()

    def _save(self):
        note = self.text.get("1.0", "end").strip()
        if self._ph_active or note == self._placeholder:
            note = ""
        self.result = {"note": note, "tag": self.tag}
        self.destroy()


def ask_text(parent, title, prompt, initial="", width=460, height=240):
    dlg = Modal(parent, title, width=width, height=height)
    wrap = tk.Frame(dlg, bg=C["card"])
    wrap.pack(fill="both", expand=True, padx=sp(24), pady=sp(20))
    tk.Label(wrap, text=prompt, font=F["h2"], bg=C["card"], fg=C["text"], anchor="w").pack(fill="x")
    entry = make_entry(wrap, width=30)
    entry.pack(fill="x", ipady=sp(6), pady=(sp(10), 0))
    entry.insert(0, initial)

    btns = tk.Frame(wrap, bg=C["card"])
    btns.pack(fill="x", pady=(sp(16), 0))

    def ok(_e=None):
        dlg.result = entry.get().strip()
        dlg.destroy()

    RoundButton(btns, "确定", command=ok, width=110, height=40, parent_bg=C["card"]).pack(side="left")
    RoundButton(btns, "取消", command=dlg._cancel, width=90, height=40, bg=C["card3"],
                fg=C["dim"], parent_bg=C["card"]).pack(side="left", padx=sp(8))
    entry.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda _e: dlg._cancel())
    dlg.after(100, entry.focus_set)
    return dlg.show()


def ask_choice(parent, title, message, options):
    """options: [(按钮文字, 颜色)]；返回被点击的下标，取消返回 None。"""
    dlg = Modal(parent, title, width=540, height=240)
    wrap = tk.Frame(dlg, bg=C["card"])
    wrap.pack(fill="both", expand=True, padx=sp(24), pady=sp(20))
    tk.Label(wrap, text=message, font=F["body"], bg=C["card"], fg=C["text"],
             wraplength=sp(470), justify="left", anchor="w").pack(fill="x")
    btns = tk.Frame(wrap, bg=C["card"])
    btns.pack(fill="x", side="bottom", pady=(sp(18), 0))
    for idx, (label, color) in enumerate(options):
        fg = "#ffffff" if color == C["accent"] else C["dim"]
        RoundButton(btns, label, command=lambda i=idx: _choose(dlg, i), width=138, height=40,
                    bg=color, fg=fg, parent_bg=C["card"]).pack(side="left", padx=(0, sp(8)))
    dlg.bind("<Escape>", lambda _e: dlg._cancel())
    return dlg.show()


def _choose(dlg, idx):
    dlg.result = idx
    dlg.destroy()


class TodoDialog(Modal):
    """新增 / 编辑待办。"""

    def __init__(self, parent, todo=None, default_due=""):
        super().__init__(parent, "编辑待办" if todo else "新建待办", width=540, height=400)
        self._todo = todo or {}
        wrap = tk.Frame(self, bg=C["card"])
        wrap.pack(fill="both", expand=True, padx=sp(24), pady=sp(20))

        tk.Label(wrap, text="待办内容", font=F["small"], bg=C["card"], fg=C["mute"],
                 anchor="w").pack(fill="x")
        self.title_entry = make_entry(wrap, width=40)
        self.title_entry.pack(fill="x", ipady=sp(6), pady=(sp(4), sp(12)))
        self.title_entry.insert(0, self._todo.get("title", ""))

        grid = tk.Frame(wrap, bg=C["card"])
        grid.pack(fill="x")
        for i, label in enumerate(("截止日期", "优先级", "标签")):
            tk.Label(grid, text=label, font=F["small"], bg=C["card"], fg=C["mute"],
                     anchor="w").grid(row=0, column=i, sticky="w", padx=(0, sp(12)))
        self.due_entry = make_entry(grid, width=14)
        self.due_entry.grid(row=1, column=0, sticky="w", ipady=sp(5))
        self.due_entry.insert(0, self._todo.get("due", default_due or ""))

        labels = [PRIORITY_LABEL[p] for p in PRIORITIES]
        current = PRIORITY_LABEL.get(self._todo.get("priority", "mid"), "中")
        self.prio = Dropdown(grid, labels, current, width=5)
        self.prio.grid(row=1, column=1, sticky="w", padx=(0, sp(12)), ipady=sp(2))

        self.tag_entry = make_entry(grid, width=14)
        self.tag_entry.grid(row=1, column=2, sticky="w", ipady=sp(5))
        self.tag_entry.insert(0, self._todo.get("tag", ""))

        tk.Label(wrap, text="日期留空表示「哪天都行」；格式 2026-11-09", font=F["tiny"],
                 bg=C["card"], fg=C["mute"], anchor="w").pack(fill="x", pady=(sp(8), 0))

        btns = tk.Frame(wrap, bg=C["card"])
        btns.pack(fill="x", side="bottom")
        RoundButton(btns, "保存", command=self._save, width=110, height=40,
                    parent_bg=C["card"]).pack(side="left")
        RoundButton(btns, "取消", command=self._cancel, width=90, height=40, bg=C["card3"],
                    fg=C["dim"], parent_bg=C["card"]).pack(side="left", padx=sp(8))

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self._cancel())
        self.after(90, self.title_entry.focus_set)

    def _save(self):
        title = self.title_entry.get().strip()
        if not title:
            self.title_entry.configure(highlightbackground=C["red"], highlightcolor=C["red"])
            return
        label_to_key = {v: k for k, v in PRIORITY_LABEL.items()}
        self.result = {
            "title": title,
            "due": self.due_entry.get().strip(),
            "priority": label_to_key.get(self.prio.value, "mid"),
            "tag": self.tag_entry.get().strip(),
        }
        self.destroy()
