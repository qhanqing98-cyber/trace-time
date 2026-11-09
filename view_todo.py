"""待办清单：加任务、定日期、勾完成，支持按状态/日期筛选。"""

import tkinter as tk

from dialog import TodoDialog, ask_choice
from store import PRIORITY_COLOR, PRIORITY_LABEL, today_str
from theme import C, F, sp
from widgets import (CheckCircle, Chip, Dropdown, Glass, Pill, Plate, RoundButton,
                     ScrollFrame, make_entry)

FILTERS = ("全部", "未完成", "今日", "已完成")


class TodoView(tk.Frame):
    def __init__(self, master, store, app=None):
        super().__init__(master, bg=C["bg"])
        self.store = store
        self.app = app
        self.filter = "全部"
        self._chips = {}
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ 布局
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = Glass(self, padx=24, pady=20)
        top.grid(row=0, column=0, sticky="ew", padx=sp(20), pady=(sp(16), sp(9)))
        body = top.body

        head = tk.Frame(body, bg=C["card"])
        head.pack(fill="x")
        tk.Label(head, text="待办", font=F["title"], bg=C["card"], fg=C["text"]).pack(side="left")
        self.summary = tk.Label(head, text="", font=F["small"], bg=C["card"], fg=C["mute"])
        self.summary.pack(side="left", padx=sp(12), pady=(sp(6), 0))
        RoundButton(head, "新建（详细）", command=self._new_dialog, width=118, height=34,
                    bg=C["card3"], fg=C["text"], parent_bg=C["card"]).pack(side="right")

        add = tk.Frame(body, bg=C["card"])
        add.pack(fill="x", pady=(sp(16), 0))
        self.entry = make_entry(add, width=40)
        self.entry.pack(side="left", fill="x", expand=True, ipady=sp(7))
        self.entry.bind("<Return>", lambda _e: self._add_quick())

        self.prio_dd = Dropdown(add, ["中", "高", "低"], "中", width=4)
        self.prio_dd.pack(side="left", padx=(sp(8), 0), ipady=sp(3))

        self.date_entry = make_entry(add, width=11)
        self.date_entry.pack(side="left", padx=(sp(8), 0), ipady=sp(7))
        self.date_entry.insert(0, today_str())
        self.date_entry.bind("<Return>", lambda _e: self._add_quick())

        RoundButton(add, "添加", command=self._add_quick, width=88, height=36,
                    parent_bg=C["card"]).pack(side="left", padx=sp(8))

        tk.Label(body, text="回车快速添加 · 日期留空表示不限 · 双击标题可编辑",
                 font=F["tiny"], bg=C["card"], fg=C["mute"], anchor="w").pack(fill="x", pady=(sp(8), 0))

        bar = tk.Frame(body, bg=C["card"])
        bar.pack(fill="x", pady=(sp(12), 0))
        for name in FILTERS:
            chip = Chip(bar, name, command=self._on_filter, active=(name == self.filter),
                        parent_bg=C["card"])
            chip.pack(side="left", padx=(0, sp(6)))
            self._chips[name] = chip
        RoundButton(bar, "清空已完成", command=self._clear_done, width=112, height=30,
                    bg=C["card3"], fg=C["mute"], parent_bg=C["card"]).pack(side="right")

        list_card = Glass(self, padx=14, pady=14)
        list_card.grid(row=1, column=0, sticky="nsew", padx=sp(20), pady=(0, sp(16)))
        self.list = ScrollFrame(list_card.body, bg=C["card"])
        self.list.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ 操作
    def _prio_key(self):
        return {"高": "high", "中": "mid", "低": "low"}.get(self.prio_dd.value, "mid")

    def _add_quick(self):
        title = self.entry.get().strip()
        if not title:
            self.entry.configure(highlightbackground=C["red"], highlightcolor=C["red"])
            return
        self.entry.configure(highlightbackground=C["line"])
        self.store.add_todo(title, due=self.date_entry.get().strip(), priority=self._prio_key())
        self.entry.delete(0, "end")

    def _new_dialog(self):
        res = TodoDialog(self, default_due=self.date_entry.get().strip() or today_str()).show()
        if res:
            self.store.add_todo(res["title"], due=res["due"], priority=res["priority"], tag=res["tag"])

    def _edit(self, todo):
        res = TodoDialog(self, todo=todo).show()
        if res:
            self.store.update_todo(todo["id"], title=res["title"], due=res["due"],
                                   priority=res["priority"], tag=res["tag"])

    def _on_filter(self, chip):
        self.filter = chip.text
        for name, c in self._chips.items():
            c.set_active(name == self.filter)
        self.refresh()

    def _clear_done(self):
        done = sum(1 for r in self.store.todos() if r.get("done"))
        if not done:
            return
        if ask_choice(self, "清空已完成", "确定删除 %d 条已完成的待办？" % done,
                      [("删除", C["red"]), ("取消", C["card3"])]) == 0:
            self.store.clear_done()

    def _delete(self, todo):
        if ask_choice(self, "删除待办", "删除「%s」？" % todo["title"],
                      [("删除", C["red"]), ("取消", C["card3"])]) == 0:
            self.store.delete_todo(todo["id"])

    # ------------------------------------------------------------------ 刷新
    def refresh(self):
        all_rows = self.store.todos()
        today = today_str()
        pending = [r for r in all_rows if not r.get("done")]
        self.summary.configure(
            text="未完成 %d · 今日到期 %d · 已完成 %d" % (
                len(pending),
                len([r for r in all_rows if r.get("due") == today and not r.get("done")]),
                len([r for r in all_rows if r.get("done")]),
            )
        )
        if self.filter == "未完成":
            rows = pending
        elif self.filter == "今日":
            rows = [r for r in all_rows if r.get("due") == today]
        elif self.filter == "已完成":
            rows = [r for r in all_rows if r.get("done")]
        else:
            rows = all_rows
        self._fill(self.store.sorted_todos(rows))

    def _fill(self, rows):
        self.list.clear()
        if not rows:
            tk.Label(self.list.inner, text="这里空着。写下一件要做的事吧。", font=F["small"],
                     bg=C["card"], fg=C["mute"]).pack(anchor="w", padx=sp(8), pady=sp(24))
            return
        for todo in rows:
            self._row(todo)

    def _row(self, todo):
        done = bool(todo.get("done"))
        outer = Plate(self.list.inner, padx=12, pady=10)
        outer.pack(fill="x", pady=sp(3))
        row = outer.body
        row.grid_columnconfigure(1, weight=1)

        CheckCircle(row, checked=done, size=24, bg=C["card2"],
                    command=lambda t=todo: self.store.toggle_todo(t["id"])).grid(
            row=0, column=0, rowspan=2, padx=(0, sp(10)), sticky="n")

        title = tk.Label(row, text=todo.get("title", ""),
                         font=F["small_strike"] if done else F["body"],
                         bg=C["card2"], fg=C["mute"] if done else C["text"],
                         anchor="w", justify="left", wraplength=sp(520))
        title.grid(row=0, column=1, sticky="w")
        title.bind("<Double-Button-1>", lambda _e, t=todo: self._edit(t))

        meta = tk.Frame(row, bg=C["card2"])
        meta.grid(row=1, column=1, sticky="w", pady=(sp(4), 0))
        if not done and todo.get("priority"):
            key = todo.get("priority", "mid")
            Pill(meta, PRIORITY_LABEL.get(key, "中") + "优先",
                 color=PRIORITY_COLOR.get(key, C["accent"]), bg=C["card2"]).pack(side="left", padx=(0, sp(6)))
        due = todo.get("due", "")
        if due:
            overdue = (not done) and due < today_str()
            Pill(meta, ("逾期 " if overdue else "") + due,
                 color=C["red"] if overdue else C["dim"], bg=C["card2"]).pack(side="left", padx=(0, sp(6)))
        if todo.get("tag"):
            Pill(meta, "#" + todo["tag"], color=C["purple"], bg=C["card2"]).pack(side="left", padx=(0, sp(6)))
        if todo.get("done_at"):
            tk.Label(meta, text="完成于 " + todo["done_at"][:10], font=F["tiny"],
                     bg=C["card2"], fg=C["mute"]).pack(side="left")

        acts = tk.Frame(row, bg=C["card2"])
        acts.grid(row=0, column=2, rowspan=2, padx=(sp(10), 0), sticky="e")
        for text, cmd, color in (("改", lambda t=todo: self._edit(t), C["dim"]),
                                 ("删", lambda t=todo: self._delete(t), C["red"])):
            btn = tk.Label(acts, text=text, font=F["small"], bg=C["card2"], fg=color,
                           cursor="hand2", padx=sp(6), pady=sp(4))
            btn.pack(side="left", padx=sp(2))
            btn.bind("<Button-1>", lambda _e, c=cmd: c())
            btn.bind("<Enter>", lambda e: e.widget.configure(bg=C["card3"]))
            btn.bind("<Leave>", lambda e: e.widget.configure(bg=C["card2"]))
