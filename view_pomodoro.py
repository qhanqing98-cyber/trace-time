"""番茄钟：专注 / 短休 / 长休循环，番茄结束时同样记录做了什么。"""

import time
import tkinter as tk
from datetime import datetime, timedelta

from dialog import NoteDialog
from store import fmt_clock, fmt_span, today_str
from theme import C, F, MONO, mix, sp
from widgets import Glass, Pill, Plate, RoundButton, ScrollFrame, divider

PHASE_KEY = {"focus": ("专注中", "orange"), "short": ("短休息", "green"), "long": ("长休息", "accent")}


class PomodoroView(tk.Frame):
    RING = 300

    def __init__(self, master, store, app=None):
        super().__init__(master, bg=C["bg"])
        self.store = store
        self.app = app
        self.phase = "focus"
        self.total = 0
        self.remaining = 0.0
        self.running = False
        self.cycle = store.pomodoro_count(today_str()) % max(1, int(store.pomo().get("long_every", 4)))
        self._last = 0.0
        self._after = None
        self._last_draw_sec = None
        self._asking = False
        self._build()
        self.set_phase("focus")
        self.refresh()
        self._tick()

    # ------------------------------------------------------------------ 布局
    def _build(self):
        self.grid_columnconfigure(0, weight=3, uniform="col")
        self.grid_columnconfigure(1, weight=2, uniform="col")
        self.grid_rowconfigure(0, weight=1)

        left = Glass(self, padx=24, pady=22)
        left.grid(row=0, column=0, sticky="nsew", padx=(sp(20), sp(9)), pady=sp(16))
        body = left.body

        head = tk.Frame(body, bg=C["card"])
        head.pack(fill="x")
        tk.Label(head, text="番茄钟", font=F["title"], bg=C["card"], fg=C["text"]).pack(side="left")
        self.phase_pill = Pill(head, "专注中", color=C["orange"], bg=C["card"], font=F["small"])
        self.phase_pill.pack(side="left", padx=sp(10), pady=(sp(6), 0))
        self.cycle_lbl = tk.Label(head, text="", font=F["small"], bg=C["card"], fg=C["mute"])
        self.cycle_lbl.pack(side="right", pady=(sp(8), 0))

        size = sp(self.RING)
        self.ring = tk.Canvas(body, width=size, height=size, bg=C["card"], highlightthickness=0, bd=0)
        self.ring.pack(pady=(sp(12), sp(6)))

        btns = tk.Frame(body, bg=C["card"])
        btns.pack(pady=(sp(4), 0))
        self.toggle_btn = RoundButton(btns, "开始专注", command=self._toggle, width=150, height=46,
                                      parent_bg=C["card"])
        self.toggle_btn.pack(side="left")
        self.skip_btn = RoundButton(btns, "跳过", command=self._skip, width=96, height=46,
                                    bg=C["card3"], fg=C["text"], parent_bg=C["card"])
        self.skip_btn.pack(side="left", padx=sp(10))
        self.reset_btn = RoundButton(btns, "重置", command=self._reset, width=96, height=46,
                                     bg=C["card3"], fg=C["mute"], parent_bg=C["card"])
        self.reset_btn.pack(side="left")

        tk.Label(body, text="一个番茄结束时会弹出输入框，写下这段时间你做了什么。",
                 font=F["tiny"], bg=C["card"], fg=C["mute"]).pack(pady=(sp(14), 0))

        # ------------------------------------------------------------ 右侧
        right = Glass(self, padx=18, pady=18)
        right.grid(row=0, column=1, sticky="nsew", padx=(sp(9), sp(20)), pady=sp(16))
        rbody = right.body

        stat = Plate(rbody, padx=14, pady=12)
        stat.pack(fill="x")
        self.count_lbl = tk.Label(stat.body, text="0", font=F["num"], bg=C["card2"], fg=C["orange"])
        self.count_lbl.pack(side="left")
        tk.Label(stat.body, text="个番茄", font=F["small"], bg=C["card2"],
                 fg=C["dim"]).pack(side="left", padx=(sp(8), 0))
        self.focus_lbl = tk.Label(stat.body, text="专注 0 分", font=F["small"],
                                  bg=C["card2"], fg=C["mute"])
        self.focus_lbl.pack(side="right")

        tk.Label(rbody, text="参数设置", font=F["h2"], bg=C["card"], fg=C["text"],
                 anchor="w").pack(fill="x", pady=(sp(16), sp(8)))
        grid = tk.Frame(rbody, bg=C["card"])
        grid.pack(fill="x")
        pomo = self.store.pomo()
        self.spin = {}
        rows = [("focus", "专注（分）", 1, 180), ("short", "短休（分）", 1, 60),
                ("long", "长休（分）", 1, 90), ("long_every", "长休间隔（个）", 1, 12)]
        for i, (key, label, lo, hi) in enumerate(rows):
            tk.Label(grid, text=label, font=F["small"], bg=C["card"], fg=C["dim"],
                     anchor="w").grid(row=i, column=0, sticky="w", pady=sp(3))
            var = tk.StringVar(value=str(pomo.get(key, 25)))
            spin = tk.Spinbox(
                grid, from_=lo, to=hi, textvariable=var, width=5, font=F["mono"],
                bg=C["card2"], fg=C["text"], buttonbackground=C["card2"],
                insertbackground=C["text"], relief="flat", bd=0, highlightthickness=1,
                highlightbackground=mix(C["card2"], "#ffffff", 0.08), highlightcolor=C["accent"],
                justify="center", command=self._apply_settings,
            )
            spin.grid(row=i, column=1, sticky="ew", padx=(sp(8), 0), pady=sp(3), ipady=sp(2))
            spin.bind("<Return>", lambda _e: self._apply_settings())
            spin.bind("<FocusOut>", lambda _e: self._apply_settings())
            self.spin[key] = var
        grid.grid_columnconfigure(1, weight=1)

        opts = tk.Frame(rbody, bg=C["card"])
        opts.pack(fill="x", pady=(sp(10), 0))
        self.auto_var = tk.BooleanVar(value=bool(pomo.get("auto_next", True)))
        self.sound_var = tk.BooleanVar(value=bool(pomo.get("sound", True)))
        for var, text, key in ((self.auto_var, "自动开始下一阶段", "auto_next"),
                               (self.sound_var, "阶段结束提示音", "sound")):
            cb = tk.Checkbutton(
                opts, text=text, variable=var, font=F["small"], bg=C["card"], fg=C["dim"],
                activebackground=C["card"], activeforeground=C["text"], selectcolor=C["card2"],
                bd=0, highlightthickness=0, cursor="hand2",
                command=lambda k=key, v=var: self.store.set_pomo(k, bool(v.get())),
            )
            cb.pack(anchor="w")

        divider(rbody, pady=(sp(14), sp(10)))

        tk.Label(rbody, text="今日番茄记录", font=F["h2"], bg=C["card"], fg=C["text"],
                 anchor="w").pack(fill="x")
        self.list = ScrollFrame(rbody, bg=C["card"])
        self.list.pack(fill="both", expand=True, pady=(sp(8), 0))

    # ------------------------------------------------------------------ 状态
    def _phase_seconds(self, phase):
        pomo = self.store.pomo()
        minutes = {"focus": pomo.get("focus", 25), "short": pomo.get("short", 5),
                   "long": pomo.get("long", 15)}[phase]
        return max(1, int(minutes)) * 60

    def set_phase(self, phase, keep_running=False):
        self.phase = phase
        self.total = self._phase_seconds(phase)
        self.remaining = float(self.total)
        self.running = keep_running
        self._last = time.monotonic()
        self._last_draw_sec = None
        label, color_key = PHASE_KEY[phase]
        self.phase_pill.set(text=label, color=C[color_key], bg=C["card"])
        self.toggle_btn.set_text("暂停" if keep_running else ("开始专注" if phase == "focus" else "开始休息"))
        self.toggle_btn.set_colors(bg=C["card3"] if keep_running else C["accent"],
                                  fg=C["text"] if keep_running else "#ffffff")
        long_every = max(1, int(self.store.pomo().get("long_every", 4)))
        shown = self.cycle + 1 if phase == "focus" else self.cycle
        self.cycle_lbl.configure(text="第 %d / %d 个番茄" % (min(shown, long_every), long_every))
        self._draw(force=True)

    def _draw(self, force=False):
        sec = int(self.remaining + 0.999)
        if not force and sec == self._last_draw_sec:
            return
        self._last_draw_sec = sec
        c = self.ring
        c.delete("all")
        size = sp(self.RING)
        pad = sp(26)
        thick = sp(14)
        accent = C[PHASE_KEY[self.phase][1]]
        c.create_arc(pad, pad, size - pad, size - pad, start=90, extent=-359.9, style="arc",
                     outline=mix(C["card"], "#ffffff", 0.08), width=thick)
        frac = 0.0 if not self.total else max(0.0, min(1.0, 1 - self.remaining / self.total))
        if frac > 0.001:
            c.create_arc(pad, pad, size - pad, size - pad, start=90, extent=-359.9 * frac,
                         style="arc", outline=accent, width=thick)
        c.create_text(size / 2, size / 2 - sp(10), text=fmt_clock(sec), font=F["pomo"], fill=C["text"])
        c.create_text(size / 2, size / 2 + sp(34), text=PHASE_KEY[self.phase][0],
                      font=F["small"], fill=C["dim"])
        long_every = max(1, int(self.store.pomo().get("long_every", 4)))
        dots = min(long_every, 8)
        step = sp(16)
        x0 = size / 2 - (dots - 1) * step / 2
        y = size - sp(46)
        for i in range(dots):
            filled = i < self.cycle
            r = sp(4)
            c.create_oval(x0 + i * step - r, y - r, x0 + i * step + r, y + r,
                          fill=accent if filled else mix(C["card"], "#ffffff", 0.12), outline="")

    def _toggle(self):
        if self.running:
            self.running = False
            self.toggle_btn.set_text("继续")
            self.toggle_btn.set_colors(bg=C["accent"], fg="#ffffff")
        else:
            self.running = True
            self._last = time.monotonic()
            self.toggle_btn.set_text("暂停")
            self.toggle_btn.set_colors(bg=C["card3"], fg=C["text"])
        self._draw(force=True)

    def _skip(self):
        self.running = False
        self._advance(self.phase, count=False)

    def _reset(self):
        self.running = False
        self.set_phase("focus")

    def _advance(self, finished, count=True):
        """只做阶段切换，不弹任何窗（弹窗交给下游的 after，避免卡住计时回调）。"""
        long_every = max(1, int(self.store.pomo().get("long_every", 4)))
        if finished == "focus":
            if count:
                self.cycle += 1
            if self.cycle >= long_every:
                next_phase = "long"
                self.cycle = long_every
            else:
                next_phase = "short"
        else:
            if finished == "long":
                self.cycle = 0
            next_phase = "focus"
        auto = bool(self.store.pomo().get("auto_next", True))
        self.set_phase(next_phase, keep_running=auto)
        if auto:
            self._last = time.monotonic()

    def _ask_focus_note(self, start, end, seconds):
        """番茄结束后补记内容；这一步可能在另一个事件轮回里执行，所以格外小心。"""
        if self._asking:
            # 上一条还没填完，别再叠一个弹窗——先把这段时间记下来，内容留空
            self.store.add_segment(start, end, note="", tag="", source="pomodoro")
            return
        self._asking = True
        try:
            dlg = NoteDialog(self, start=start, end=end, seconds=seconds,
                             tags=self.store.tags(), recent=self.store.recent_notes(3),
                             source="番茄钟")
            res = dlg.show()
            if res is None:
                return
            self.store.add_segment(start, end, note=res["note"], tag=res["tag"], source="pomodoro")
        finally:
            self._asking = False

    def _apply_settings(self):
        for key, var in self.spin.items():
            try:
                val = int(float(var.get()))
            except ValueError:
                val = int(self.store.pomo().get(key, 1))
            val = max(1, val)
            var.set(str(val))
            self.store.set_pomo(key, val)
        self.store.set_pomo("auto_next", bool(self.auto_var.get()))
        self.store.set_pomo("sound", bool(self.sound_var.get()))
        if not self.running:
            self.set_phase(self.phase)

    # ------------------------------------------------------------------ 循环
    def _tick(self):
        self._after = self.after(200, self._tick)
        if not self.running:
            return
        now = time.monotonic()
        delta = now - self._last
        self._last = now
        self.remaining -= delta
        if self.remaining <= 0:
            self.remaining = 0
            self.running = False
            self._draw(force=True)
            self._on_phase_end()
            return
        self._draw()

    def _on_phase_end(self):
        finished = self.phase
        seconds = int(self.total)
        end = datetime.now()
        start = end - timedelta(seconds=seconds)
        if bool(self.store.pomo().get("sound", True)):
            self._beep()
        # 先把状态推进到下一阶段（计时继续跑），再另起一个空闲回合去问「做了什么」
        self._advance(finished)
        self.refresh()
        if finished != "focus":
            return
        if self.app is not None:
            try:
                if self.app.state() == "iconic":
                    self.app.deiconify()
                    self.app.lift()
            except tk.TclError:
                pass
        self.after(60, lambda: self._ask_focus_note(start, end, seconds))

    def _beep(self):
        if self.app is not None and hasattr(self.app, "notify_user"):
            self.app.notify_user()
        else:
            try:
                self.bell()
            except tk.TclError:
                pass

    def destroy(self):
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        super().destroy()

    # -------------------------------------------------------------- 主题切换
    def snapshot(self):
        return {"phase": self.phase, "remaining": self.remaining, "total": self.total,
                "running": self.running, "cycle": self.cycle}

    def restore(self, snap):
        self.phase = snap.get("phase", "focus")
        self.total = snap.get("total") or self._phase_seconds(self.phase)
        self.remaining = snap.get("remaining", self.total)
        self.cycle = snap.get("cycle", 0)
        self.set_phase(self.phase, keep_running=bool(snap.get("running")))
        self.remaining = snap.get("remaining", self.total)
        self._last = time.monotonic()
        self._draw(force=True)

    # ------------------------------------------------------------------ 刷新
    def refresh(self):
        day = today_str()
        count = self.store.pomodoro_count(day)
        seconds = self.store.total_seconds(day, source="pomodoro")
        self.count_lbl.configure(text=str(count))
        self.focus_lbl.configure(text="专注 %s" % fmt_span(seconds))
        self._fill_list(day)

    def _fill_list(self, day):
        self.list.clear()
        segs = [s for s in self.store.segments(day) if s.get("source") == "pomodoro"]
        if not segs:
            tk.Label(self.list.inner, text="今天还没有完成的番茄。", font=F["small"],
                     bg=C["card"], fg=C["mute"]).pack(anchor="w", padx=sp(6), pady=sp(18))
            return
        for seg in segs:
            row = Plate(self.list.inner, padx=10, pady=7)
            row.pack(fill="x", pady=sp(3))
            inner = row.body
            top = tk.Frame(inner, bg=C["card2"])
            top.pack(fill="x")
            tk.Label(top, text="●", font=F["tiny"], bg=C["card2"], fg=C["orange"]).pack(side="left")
            tk.Label(top, text="%s – %s" % (seg.get("start", ""), seg.get("end", "")),
                     font=F["mono_sm"], bg=C["card2"], fg=C["dim"]).pack(side="left", padx=sp(6))
            tk.Label(top, text=fmt_span(seg.get("seconds", 0)), font=F["tiny"],
                     bg=C["card2"], fg=C["mute"]).pack(side="right")
            tk.Label(inner, text=seg.get("note") or "（没有写内容）", font=F["small"], bg=C["card2"],
                     fg=C["text"] if seg.get("note") else C["mute"], anchor="w",
                     justify="left", wraplength=sp(260)).pack(fill="x", pady=(sp(4), 0))
