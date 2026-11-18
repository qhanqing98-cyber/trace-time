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
        self._rows = {}      # 待办 id → 这一行上的控件，用来原地更新而不是推倒重搭
        self._rows_key = None
        self._empty = None
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
        """按内容差异增量更新。

        Tk 销毁一个控件要 2–4 ms，原来每次刷新都把整表拆了重搭：
        20 条待办约 200 个控件，光是销毁就要 0.4–0.8 秒，每切回待办页都卡一下。
        现在没变的行为一个控件都不动，变了的行原地改属性。
        """
        key = tuple((t.get("id"), self._sig(t)) for t in rows)
        if key == self._rows_key:
            return
        self._rows_key = key

        if self._empty is not None:
            self._empty.destroy()
            self._empty = None

        keep = set()
        for todo in rows:
            tid = todo.get("id")
            handles = self._rows.get(tid)
            if handles is None:
                handles = self._row(todo)
                self._rows[tid] = handles
            elif handles["sig"] != self._sig(todo):
                self._update_row(handles, todo)
            keep.add(tid)
            handles["outer"].pack(fill="x", pady=sp(3))  # 按新顺序重排（pack 顺序即显示顺序）

        # 不在当前筛选里的行先藏起来留着下次用——销毁一个控件比藏起来贵上百倍，
        # 只有待办真的被删掉了才销毁。
        alive = {t.get("id") for t in self.store.todos()}
        for tid, handles in list(self._rows.items()):
            if tid in keep:
                continue
            if tid in alive:
                handles["outer"].pack_forget()
            else:
                handles["outer"].destroy()
                del self._rows[tid]

        if not rows:
            self._empty = tk.Label(self.list.inner, text="这里空着。写下一件要做的事吧。",
                                   font=F["small"], bg=C["card"], fg=C["mute"])
            self._empty.pack(anchor="w", padx=sp(8), pady=sp(24))

    # ------------------------------------------------------------ 一行的拆解
    @staticmethod
    def _sig(todo):
        """换行需要的全部信息：任何一项变了，这一行才需要动。"""
        return (bool(todo.get("done")), todo.get("title") or "", todo.get("due") or "",
                todo.get("priority") or "", todo.get("tag") or "", todo.get("done_at") or "")

    def _meta_sig(self, todo):
        return (bool(todo.get("done")), todo.get("priority") or "", todo.get("due") or "",
                todo.get("tag") or "", todo.get("done_at") or "")

    def _find(self, tid):
        for rec in self.store.todos():
            if rec.get("id") == tid:
                return rec
        return None

    def _edit_id(self, tid):
        todo = self._find(tid)
        if todo is not None:
            self._edit(todo)

    def _delete_id(self, tid):
        todo = self._find(tid)
        if todo is not None:
            self._delete(todo)

    def _row(self, todo):
        done = bool(todo.get("done"))
        outer = Plate(self.list.inner, padx=12, pady=10)
        outer.pack(fill="x", pady=sp(3))
        row = outer.body
        row.grid_columnconfigure(1, weight=1)

        check = CheckCircle(row, checked=done, size=24, bg=C["card2"],
                            command=lambda tid=todo.get("id"): self.store.toggle_todo(tid))
        check.grid(row=0, column=0, rowspan=2, padx=(0, sp(10)), sticky="n")

        title = tk.Label(row, text=todo.get("title", ""),
                         font=F["small_strike"] if done else F["body"],
                         bg=C["card2"], fg=C["mute"] if done else C["text"],
                         anchor="w", justify="left", wraplength=sp(520))
        title.grid(row=0, column=1, sticky="w")
        title.bind("<Double-Button-1>", lambda _e, tid=todo.get("id"): self._edit_id(tid))

        meta = tk.Frame(row, bg=C["card2"])
        meta.grid(row=1, column=1, sticky="w", pady=(sp(4), 0))
        self._fill_meta(meta, todo)

        acts = tk.Frame(row, bg=C["card2"])
        acts.grid(row=0, column=2, rowspan=2, padx=(sp(10), 0), sticky="e")
        for text, cmd, color in (("改", lambda tid=todo.get("id"): self._edit_id(tid), C["dim"]),
                                 ("删", lambda tid=todo.get("id"): self._delete_id(tid), C["red"])):
            btn = tk.Label(acts, text=text, font=F["small"], bg=C["card2"], fg=color,
                           cursor="hand2", padx=sp(6), pady=sp(4))
            btn.pack(side="left", padx=sp(2))
            btn.bind("<Button-1>", lambda _e, c=cmd: c())
            btn.bind("<Enter>", lambda e: e.widget.configure(bg=C["card3"]))
            btn.bind("<Leave>", lambda e: e.widget.configure(bg=C["card2"]))

        return {"outer": outer, "check": check, "title": title, "meta": meta,
                "sig": self._sig(todo), "meta_sig": self._meta_sig(todo)}

    def _update_row(self, handles, todo):
        """行还在，只是内容变了：改属性比重建便宜两个数量级。"""
        done = bool(todo.get("done"))
        handles["check"].set(done)
        handles["title"].configure(
            text=todo.get("title", ""),
            font=F["small_strike"] if done else F["body"],
            fg=C["mute"] if done else C["text"],
        )
        meta_sig = self._meta_sig(todo)
        if meta_sig != handles["meta_sig"]:
            handles["meta_sig"] = meta_sig
            self._fill_meta(handles["meta"], todo)
        handles["sig"] = self._sig(todo)

    def _fill_meta(self, meta, todo):
        """优先级 / 日期 / 标签这几个小胶囊，只在它们变了的时候重建。"""
        for child in meta.winfo_children():
            child.destroy()
        done = bool(todo.get("done"))
        if not done and todo.get("priority"):
            key = todo.get("priority", "mid")
            Pill(meta, PRIORITY_LABEL.get(key, "中") + "优先",
                 color=PRIORITY_COLOR.get(key, C["accent"]), bg=C["card2"]).pack(
                side="left", padx=(0, sp(6)))
        due = todo.get("due", "")
        if due:
            overdue = (not done) and due < today_str()
            Pill(meta, ("逾期 " if overdue else "") + due,
                 color=C["red"] if overdue else C["dim"], bg=C["card2"]).pack(
                side="left", padx=(0, sp(6)))
        if todo.get("tag"):
            Pill(meta, "#" + todo["tag"], color=C["purple"], bg=C["card2"]).pack(
                side="left", padx=(0, sp(6)))
        if todo.get("done_at"):
            tk.Label(meta, text="完成于 " + todo["done_at"][:10], font=F["tiny"],
                     bg=C["card2"], fg=C["mute"]).pack(side="left")
