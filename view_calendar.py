"""日历：月视图热力图 + 选中某天的待办、专注时长与时间线。"""

import calendar as cal
import tkinter as tk
from datetime import date

from dialog import TodoDialog
from store import fmt_span
from theme import C, F, MONO, mix, sp
from widgets import (CheckCircle, Glass, Pill, Plate, RoundButton, ScrollFrame,
                     divider, round_poly)

WEEK_LABELS = ("一", "二", "三", "四", "五", "六", "日")
WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


class CalendarView(tk.Frame):
    def __init__(self, master, store, app=None):
        super().__init__(master, bg=C["bg"])
        self.store = store
        self.app = app
        today = date.today()
        start = getattr(app, "_cal_day", None) or today
        self.year, self.month = start.year, start.month
        self.selected = start
        self.cells = []
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ 布局
    def _build(self):
        self.grid_columnconfigure(0, weight=3, uniform="col")
        self.grid_columnconfigure(1, weight=2, uniform="col")
        self.grid_rowconfigure(0, weight=1)

        left = Glass(self, padx=20, pady=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(sp(20), sp(9)), pady=sp(16))
        body = left.body

        head = tk.Frame(body, bg=C["card"])
        head.pack(fill="x")
        RoundButton(head, "‹", command=lambda: self._shift_month(-1), width=34, height=32,
                    bg=C["card3"], fg=C["text"], parent_bg=C["card"], radius=sp(9),
                    font=F["h2"]).pack(side="left")
        self.month_lbl = tk.Label(head, text="", font=F["h1"], bg=C["card"], fg=C["text"])
        self.month_lbl.pack(side="left", padx=sp(12))
        RoundButton(head, "›", command=lambda: self._shift_month(1), width=34, height=32,
                    bg=C["card3"], fg=C["text"], parent_bg=C["card"], radius=sp(9),
                    font=F["h2"]).pack(side="left")
        RoundButton(head, "回到今天", command=self._go_today, width=96, height=32,
                    bg=C["card3"], fg=C["dim"], parent_bg=C["card"]).pack(side="left", padx=sp(10))

        legend = tk.Frame(head, bg=C["card"])
        legend.pack(side="right")
        for color, text in ((C["orange"], "待办"), (C["green"], "番茄")):
            tk.Label(legend, text="●", font=F["tiny"], bg=C["card"], fg=color).pack(side="left")
            tk.Label(legend, text=text, font=F["tiny"], bg=C["card"],
                     fg=C["mute"]).pack(side="left", padx=(0, sp(10)))

        divider(body, pady=(sp(12), sp(10)))

        week = tk.Frame(body, bg=C["card"])
        week.pack(fill="x")
        for i, name in enumerate(WEEK_LABELS):
            week.grid_columnconfigure(i, weight=1, uniform="dow")
            tk.Label(week, text=name, font=F["small"], bg=C["card"], fg=C["mute"]).grid(
                row=0, column=i, sticky="ew", pady=(0, sp(6)))

        tk.Label(body, text="格子颜色越深 = 那天专注时间越长", font=F["tiny"],
                 bg=C["card"], fg=C["mute"], anchor="w").pack(side="bottom", fill="x", pady=(sp(8), 0))

        self.grid_frame = tk.Frame(body, bg=C["card"])
        self.grid_frame.pack(fill="both", expand=True)
        self.grid_canvas = tk.Canvas(self.grid_frame, width=1, height=sp(400), bg=C["card"],
                                     highlightthickness=0, bd=0)
        self.grid_canvas.pack(fill="both", expand=True)
        self.grid_canvas.bind("<Configure>", lambda _e: self._draw_grid())
        self.grid_canvas.bind("<Button-1>", self._on_grid_click)
        self._day_rects = []

        right = Glass(self, padx=16, pady=16)
        right.grid(row=0, column=1, sticky="nsew", padx=(sp(9), sp(20)), pady=sp(16))
        self.detail = ScrollFrame(right.body, bg=C["card"])
        self.detail.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ 导航
    def _shift_month(self, delta):
        month = self.month + delta
        year = self.year + (month - 1) // 12
        self.year, self.month = year, (month - 1) % 12 + 1
        self.refresh()

    def _go_today(self):
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selected = today
        self.refresh()

    def _select(self, day):
        self.selected = day
        if (day.month, day.year) != (self.month, self.year):
            self.year, self.month = day.year, day.month
        if self.app is not None:
            self.app._cal_day = day
        self.refresh()

    # ------------------------------------------------------------------ 刷新
    def refresh(self):
        self.month_lbl.configure(text="%d 年 %d 月" % (self.year, self.month))
        stats = self.store.month_stats(self.year, self.month)
        self._fill_grid(stats)
        self._fill_detail()

    def _create_cells(self):
        pass

    def _on_grid_click(self, event):
        for x1, y1, x2, y2, day in self._day_rects:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2 and day is not None:
                self._select(day)
                return

    def _draw_grid(self):
        """整月一次性画在一个 Canvas 上，比 42 个控件快一个数量级。"""
        c = self.grid_canvas
        c.delete("all")
        self._day_rects = []
        w, h = c.winfo_width(), c.winfo_height()
        if w < sp(60) or h < sp(60):
            return

        today = date.today()
        stats = self.store.month_stats(self.year, self.month)
        weeks = cal.Calendar(firstweekday=0).monthdatescalendar(self.year, self.month)
        while len(weeks) < 6:
            weeks.append([None] * 7)
        days = [d for week in weeks[:6] for d in week]
        values = [stats.get(d.isoformat(), {}) if d else {} for d in days]
        max_minutes = max([v.get("seconds", 0) for v in values] + [1]) / 60.0

        gap = sp(3)
        cw = (w - 6 * gap) / 7.0
        ch = (h - 5 * gap) / 6.0
        radius = sp(8)

        for idx, day in enumerate(days):
            col, row = idx % 7, idx // 7
            x1 = col * (cw + gap)
            y1 = row * (ch + gap)
            x2, y2 = x1 + cw, y1 + ch
            if day is None:
                continue
            stat = values[idx]
            minutes = stat.get("seconds", 0) / 60.0
            heat = 0.0 if not minutes else min(1.0, minutes / max(20.0, max_minutes))
            fill = C["card2"] if not minutes else mix(C["card2"], C["accent"], 0.10 + 0.34 * heat)
            selected = day == self.selected
            edge = C["accent"] if selected else mix(C["card2"], "#ffffff", 0.06)
            round_poly(c, x1, y1, x2, y2, radius, fill=fill, outline=edge,
                       width=max(1, sp(1.4)) if selected else 1)

            num_color = C["text"]
            if day == today:
                num_color = C["accent"]
            if selected:
                num_color = C["white"]
            c.create_text(x1 + sp(8), y1 + sp(5), text=str(day.day), anchor="nw",
                          font=F["mono"], fill=num_color)
            if minutes >= 1:
                label = ("%dh%02d" % (int(minutes // 60), int(minutes % 60))
                         if minutes >= 60 else "%dm" % int(minutes))
                c.create_text(x2 - sp(8), y1 + sp(6), text=label, anchor="ne",
                              font=F["tiny"], fill=C["dim"])

            dots_x = x1 + sp(8)
            dots_y = y2 - sp(7)
            for _ in range(min(self.store.pending_count(day.isoformat()), 3)):
                c.create_oval(dots_x, dots_y - sp(3), dots_x + sp(6), dots_y + sp(3),
                              fill=C["orange"], outline="")
                dots_x += sp(9)
            for _ in range(min(stat.get("pomodoro", 0), 2)):
                c.create_oval(dots_x, dots_y - sp(3), dots_x + sp(6), dots_y + sp(3),
                              fill=C["green"], outline="")
                dots_x += sp(9)
            self._day_rects.append((x1, y1, x2, y2, day))

    def _fill_grid(self, stats):
        self._draw_grid()

    def _fill_detail(self):
        self.detail.clear()
        wrap = self.detail.inner
        day = self.selected
        day_key = day.isoformat()
        stats = self.store.day_stats(day_key)

        head = tk.Frame(wrap, bg=C["card"])
        head.pack(fill="x")
        tk.Label(head, text="%d 月 %d 日" % (day.month, day.day), font=F["h1"],
                 bg=C["card"], fg=C["text"]).pack(side="left")
        tk.Label(head, text=WEEKDAY_CN[day.weekday()], font=F["small"], bg=C["card"],
                 fg=C["mute"]).pack(side="left", padx=sp(8), pady=(sp(4), 0))
        if day == date.today():
            Pill(head, "今天", color=C["green"], bg=C["card"]).pack(side="left", padx=sp(4), pady=(sp(2), 0))

        meta = tk.Frame(wrap, bg=C["card"])
        meta.pack(fill="x", pady=(sp(8), 0))
        for text, color in (("专注 %s" % fmt_span(stats["seconds"]), C["accent"]),
                            ("番茄 %d 个" % stats["pomodoro"], C["orange"]),
                            ("记录 %d 段" % stats["count"], C["dim"])):
            Pill(meta, text, color=color, bg=C["card"], font=F["small"]).pack(side="left", padx=(0, sp(6)))

        divider(wrap, pady=(sp(12), sp(8)))

        todos_here = self.store.sorted_todos(self.store.todos_for(day_key))
        tk.Label(wrap, text="待办（%d）" % len(todos_here), font=F["h2"], bg=C["card"],
                 fg=C["text"], anchor="w").pack(fill="x")
        if not todos_here:
            tk.Label(wrap, text="这天没有待办。", font=F["small"], bg=C["card"],
                     fg=C["mute"], anchor="w").pack(fill="x", pady=(sp(6), 0))
        for todo in todos_here:
            row = tk.Frame(wrap, bg=C["card"])
            row.pack(fill="x", pady=sp(3))
            CheckCircle(row, checked=bool(todo.get("done")), size=20, bg=C["card"],
                        command=lambda t=todo: self.store.toggle_todo(t["id"])).pack(side="left", pady=sp(2))
            tk.Label(row, text=todo.get("title", ""),
                     font=F["small_strike"] if todo.get("done") else F["small"],
                     bg=C["card"], fg=C["mute"] if todo.get("done") else C["text"],
                     anchor="w", justify="left", wraplength=sp(250)).pack(side="left", padx=sp(8),
                                                                         fill="x", expand=True)

        RoundButton(wrap, "＋ 在这天加一条待办", command=lambda: self._add_here(day), width=170,
                    height=32, bg=C["card3"], fg=C["dim"], parent_bg=C["card"]).pack(
            anchor="w", pady=(sp(8), 0))

        divider(wrap, pady=(sp(14), sp(8)))

        segs = self.store.segments(day_key)
        tk.Label(wrap, text="时间线（%d）" % len(segs), font=F["h2"], bg=C["card"],
                 fg=C["text"], anchor="w").pack(fill="x")
        if not segs:
            tk.Label(wrap, text="这天没有时间记录。", font=F["small"], bg=C["card"],
                     fg=C["mute"], anchor="w").pack(fill="x", pady=(sp(6), 0))
        for seg in segs:
            row = Plate(wrap, padx=10, pady=7)
            row.pack(fill="x", pady=sp(3))
            inner = row.body
            top = tk.Frame(inner, bg=C["card2"])
            top.pack(fill="x")
            color = C["orange"] if seg.get("source") == "pomodoro" else C["accent"]
            tk.Label(top, text="●", font=F["tiny"], bg=C["card2"], fg=color).pack(side="left")
            tk.Label(top, text="%s – %s" % (seg.get("start", ""), seg.get("end", "")),
                     font=F["mono_sm"], bg=C["card2"], fg=C["dim"]).pack(side="left", padx=sp(6))
            tk.Label(top, text=fmt_span(seg.get("seconds", 0)), font=F["tiny"],
                     bg=C["card2"], fg=C["mute"]).pack(side="right")
            tk.Label(inner, text=seg.get("note") or "（没有写内容）", font=F["small"], bg=C["card2"],
                     fg=C["text"] if seg.get("note") else C["mute"], anchor="w",
                     justify="left", wraplength=sp(250)).pack(fill="x", pady=(sp(4), 0))

    def _add_here(self, day):
        res = TodoDialog(self, default_due=day.isoformat()).show()
        if res:
            self.store.add_todo(res["title"], due=res["due"] or day.isoformat(),
                                priority=res["priority"], tag=res["tag"])
