"""计时器：正计时，每次暂停都要交代「这两个暂停之间你做了什么」。"""

import tkinter as tk
from datetime import datetime, timedelta

from dialog import NoteDialog
from store import fmt_clock, fmt_span, today_str
from theme import C, F, MONO, sp
from widgets import Glass, Pill, Plate, RoundButton, ScrollFrame, divider

SOURCE = {"timer": ("计时", "accent"), "pomodoro": ("番茄", "orange")}


class TimerView(tk.Frame):
    def __init__(self, master, store, app=None):
        super().__init__(master, bg=C["bg"])
        self.store = store
        self.app = app
        self.state = "idle"
        self.seg_start = None
        self.frozen = 0.0
        self.last_secs = 0
        self._after = None
        self._build()
        self.refresh()
        self._tick()

    # ------------------------------------------------------------------ 布局
    def _build(self):
        self.grid_columnconfigure(0, weight=3, uniform="col")
        self.grid_columnconfigure(1, weight=2, uniform="col")
        self.grid_rowconfigure(0, weight=1)

        left = Glass(self, padx=30, pady=26)
        left.grid(row=0, column=0, sticky="nsew", padx=(sp(20), sp(9)), pady=sp(16))
        body = left.body

        head = tk.Frame(body, bg=C["card"])
        head.pack(fill="x")
        tk.Label(head, text="计时器", font=F["title"], bg=C["card"], fg=C["text"]).pack(side="left")
        self.state_pill = Pill(head, "未开始", color=C["mute"], bg=C["card"], font=F["small"])
        self.state_pill.pack(side="left", padx=sp(10), pady=(sp(6), 0))
        tk.Label(head, text="每暂停一次，就记录一次做了什么", font=F["small"],
                 bg=C["card"], fg=C["mute"]).pack(side="right", pady=(sp(8), 0))

        self.time_lbl = tk.Label(body, text="00:00", font=F["big"], bg=C["card"],
                                 fg=C["text"], anchor="w")
        self.time_lbl.pack(fill="x", pady=(sp(22), 0))

        self.detail_lbl = tk.Label(
            body, text="点「开始」进入这一段，计时会一直走，直到你按下暂停。",
            font=F["small"], bg=C["card"], fg=C["dim"], anchor="w", justify="left",
            wraplength=sp(470),
        )
        self.detail_lbl.pack(fill="x", pady=(sp(2), sp(18)))

        divider(body)

        btns = tk.Frame(body, bg=C["card"])
        btns.pack(fill="x", pady=(sp(18), 0))
        self.primary = RoundButton(btns, "开始", command=self._primary_action,
                                   width=150, height=46, parent_bg=C["card"])
        self.primary.pack(side="left")
        self.finish_btn = RoundButton(btns, "结束并记录", command=self._finish, width=136, height=46,
                                      bg=C["card3"], fg=C["text"], parent_bg=C["card"])
        self.finish_btn.pack(side="left", padx=sp(10))
        self.reset_btn = RoundButton(btns, "重置", command=self._reset, width=92, height=46,
                                     bg=C["card3"], fg=C["mute"], parent_bg=C["card"])
        self.reset_btn.pack(side="left")

        tk.Label(body, text="快捷键：空格 开始/暂停　·　Esc 结束并记录",
                 font=F["tiny"], bg=C["card"], fg=C["mute"], anchor="w").pack(fill="x", pady=(sp(14), 0))

        stats = Plate(body, padx=16, pady=12)
        stats.pack(fill="x", side="bottom", pady=(sp(18), 0))
        self.today_total = tk.Label(stats.body, text="0 分", font=F["num"],
                                    bg=C["card2"], fg=C["green"])
        self.today_total.pack(side="left")
        tk.Label(stats.body, text="今日已记录", font=F["small"], bg=C["card2"],
                 fg=C["dim"]).pack(side="left", padx=(sp(10), 0))
        self.today_meta = tk.Label(stats.body, text="0 段", font=F["small"], bg=C["card2"], fg=C["mute"])
        self.today_meta.pack(side="right")

        # ------------------------------------------------------------ 右侧
        right = Glass(self, padx=18, pady=18)
        right.grid(row=0, column=1, sticky="nsew", padx=(sp(9), sp(20)), pady=sp(16))
        rbody = right.body
        rh = tk.Frame(rbody, bg=C["card"])
        rh.pack(fill="x")
        tk.Label(rh, text="今日时间线", font=F["h1"], bg=C["card"], fg=C["text"]).pack(side="left")
        self.tl_meta = tk.Label(rh, text="", font=F["small"], bg=C["card"], fg=C["mute"])
        self.tl_meta.pack(side="right")
        divider(rbody, pady=(sp(10), sp(8)))

        self.timeline = ScrollFrame(rbody, bg=C["card"])
        self.timeline.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ 状态
    def elapsed(self):
        if self.state == "running" and self.seg_start:
            return (datetime.now() - self.seg_start).total_seconds()
        return self.frozen

    def _set_buttons(self):
        if self.state == "idle":
            self.primary.set_text("开始")
            self.primary.set_colors(bg=C["accent"], fg="#ffffff")
            self.primary.set_enabled(True)
            self.finish_btn.set_enabled(False)
            self.reset_btn.set_enabled(False)
            self.state_pill.set(text="未开始", color=C["mute"], bg=C["card"])
            self.time_lbl.configure(fg=C["text"])
        elif self.state == "running":
            self.primary.set_text("暂停并记录")
            self.primary.set_colors(bg=C["orange"], fg="#20160a")
            self.primary.set_enabled(True)
            self.finish_btn.set_enabled(True)
            self.reset_btn.set_enabled(True)
            self.state_pill.set(text="进行中", color=C["orange"], bg=C["card"])
            self.time_lbl.configure(fg=C["text"])
        else:
            self.primary.set_text("继续下一段")
            self.primary.set_colors(bg=C["accent"], fg="#ffffff")
            self.primary.set_enabled(True)
            self.finish_btn.set_enabled(True)
            self.reset_btn.set_enabled(True)
            self.state_pill.set(text="已暂停", color=C["dim"], bg=C["card"])
            self.time_lbl.configure(fg=C["dim"])

    def _primary_action(self):
        if self.state == "running":
            self._pause()
        else:
            self._start()

    def _start(self):
        self.seg_start = datetime.now()
        self.frozen = 0.0
        self.state = "running"
        self.time_lbl.configure(text="00:00")
        self._set_buttons()
        self._update_detail()

    def _pause(self):
        seconds = self.elapsed()
        start, end = self.seg_start, datetime.now()
        self.frozen = seconds
        self.state = "paused"
        self._set_buttons()
        if seconds >= 1:
            self._log_segment(start, end, "计时器")

    def _finish(self):
        if self.state == "idle":
            return
        start = end = None
        seconds = 0
        if self.state == "running":
            start, end = self.seg_start, datetime.now()
            seconds = (end - start).total_seconds()
        self.state = "idle"
        self.seg_start = None
        self.frozen = 0.0
        self.time_lbl.configure(text="00:00")
        self._set_buttons()
        if seconds >= 1:
            self._log_segment(start, end, "计时器")
        self._update_detail()

    def _reset(self):
        self.state = "idle"
        self.seg_start = None
        self.frozen = 0.0
        self.time_lbl.configure(text="00:00")
        self._set_buttons()
        self._update_detail()

    def _log_segment(self, start, end, source_label):
        dlg = NoteDialog(self, start=start, end=end,
                         seconds=int((end - start).total_seconds()),
                         tags=self.store.tags(), recent=self.store.recent_notes(3),
                         source=source_label)
        res = dlg.show()
        if res is None:
            self.detail_lbl.configure(text="这一段没有记录（已跳过），下面继续计时即可。", fg=C["mute"])
            return
        self.store.add_segment(start, end, note=res["note"], tag=res["tag"], source="timer")
        self.last_secs = int((end - start).total_seconds())
        self.detail_lbl.configure(
            text="刚才那一段 %s 已记入时间线，点「继续下一段」接着走。" % fmt_span(self.last_secs),
            fg=C["dim"],
        )

    def _update_detail(self):
        if self.state == "running" and self.seg_start:
            self.detail_lbl.configure(
                text="本段开始于 %s，已经走了 %s —— 按暂停时会请你写下做了什么。"
                     % (self.seg_start.strftime("%H:%M"), fmt_span(self.elapsed())),
                fg=C["dim"],
            )
        elif self.state == "paused":
            self.detail_lbl.configure(
                text="已暂停。上一段 %s。" % (fmt_span(self.last_secs) if self.last_secs else "未记录"),
                fg=C["dim"],
            )
        else:
            self.detail_lbl.configure(text="点「开始」进入这一段，计时会一直走，直到你按下暂停。", fg=C["dim"])

    # ------------------------------------------------------------------ 循环
    def _tick(self):
        self._after = self.after(200, self._tick)
        if self.state == "running":
            self.time_lbl.configure(text=fmt_clock(self.elapsed()))
            if int(self.elapsed()) % 30 == 0:
                self._update_detail()

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
        return {"state": self.state, "elapsed": self.elapsed(), "last_secs": self.last_secs}

    def restore(self, snap):
        self.last_secs = snap.get("last_secs", 0)
        state = snap.get("state", "idle")
        if state == "running":
            self.seg_start = datetime.now() - timedelta(seconds=snap.get("elapsed", 0))
            self.state = "running"
        elif state == "paused":
            self.frozen = snap.get("elapsed", 0)
            self.state = "paused"
        else:
            self.state = "idle"
        self._set_buttons()
        self._update_detail()
        self.time_lbl.configure(text=fmt_clock(self.elapsed()))

    # ------------------------------------------------------------------ 刷新
    def refresh(self):
        day = today_str()
        stats = self.store.day_stats(day)
        self.today_total.configure(text=fmt_span(stats["seconds"]))
        self.today_meta.configure(text="%d 段 · 番茄 %d 个" % (stats["count"], stats["pomodoro"]))
        self.tl_meta.configure(text="合计 %s" % fmt_span(stats["seconds"]))
        self._fill_timeline(day)

    def _fill_timeline(self, day):
        self.timeline.clear()
        segs = self.store.segments(day)
        if not segs:
            tk.Label(
                self.timeline.inner,
                text="今天还没有记录。\n开始计时 → 暂停 → 写下你做了什么，这里就会出现一条。",
                font=F["small"], bg=C["card"], fg=C["mute"], justify="left",
            ).pack(anchor="w", padx=sp(6), pady=sp(28))
            return
        for seg in segs:
            self._timeline_row(seg)

    def _timeline_row(self, seg):
        row = Plate(self.timeline.inner, padx=12, pady=8)
        row.pack(fill="x", pady=sp(3))
        inner = row.body

        top = tk.Frame(inner, bg=C["card2"])
        top.pack(fill="x")
        label, color_key = SOURCE.get(seg.get("source"), ("记录", "accent"))
        Pill(top, label, color=C[color_key], bg=C["card2"]).pack(side="left")
        tk.Label(top, text="%s – %s" % (seg.get("start", ""), seg.get("end", "")),
                 font=F["mono_sm"], bg=C["card2"], fg=C["dim"]).pack(side="left", padx=sp(8))
        tk.Label(top, text=fmt_span(seg.get("seconds", 0)), font=F["tiny"],
                 bg=C["card2"], fg=C["mute"]).pack(side="right")

        note = seg.get("note") or "（没有写内容）"
        tk.Label(inner, text=note, font=F["body"], bg=C["card2"],
                 fg=C["text"] if seg.get("note") else C["mute"],
                 anchor="w", justify="left", wraplength=sp(300)).pack(fill="x", pady=(sp(6), 0))

        if seg.get("tag"):
            Pill(inner, "#" + seg["tag"], color=C["purple"], bg=C["card2"]).pack(anchor="w", pady=(sp(6), 0))

    # -------------------------------------------------------------- 快捷键支持
    def has_open_segment(self):
        return self.state == "running" and self.elapsed() >= 1
