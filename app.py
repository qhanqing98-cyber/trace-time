"""主窗口：左侧导航 + 四个视图 + 外观设置（配色 / 透明度 / 毛玻璃）。"""

import tkinter as tk

from dialog import ask_choice
from look import LookPanel
from store import Store, fmt_span, today_str
from theme import C, F, LOOK_DEFAULT, sp, style_ttk
from theme import rebuild as rebuild_theme
import winfx
from view_calendar import CalendarView
from view_pomodoro import PomodoroView
from view_timer import TimerView
from view_todo import TodoView

NAV = (
    ("timer", "计时器", "暂停时记录做了什么"),
    ("pomodoro", "番茄钟", "25 分钟一个回合"),
    ("todo", "待办", "要做的事都在这"),
    ("calendar", "日历", "回看每一天"),
)

BLUR_STRENGTH = 0x74


class NavButton(tk.Frame):
    def __init__(self, master, key, title, subtitle, command):
        super().__init__(master, bg=C["sidebar"], cursor="hand2")
        self.key = key
        self.active = False
        self.bar = tk.Frame(self, width=sp(3), bg=C["sidebar"])
        self.bar.pack(side="left", fill="y")
        inner = tk.Frame(self, bg=C["sidebar"])
        inner.pack(side="left", fill="both", expand=True, padx=(sp(13), sp(10)), pady=sp(9))
        self.title_lbl = tk.Label(inner, text=title, font=F["h2"], bg=C["sidebar"],
                                  fg=C["dim"], anchor="w")
        self.title_lbl.pack(fill="x")
        self.sub_lbl = tk.Label(inner, text=subtitle, font=F["tiny"], bg=C["sidebar"],
                                fg=C["mute"], anchor="w")
        self.sub_lbl.pack(fill="x")
        self._parts = [self, inner, self.title_lbl, self.sub_lbl]
        for widget in self._parts:
            widget.bind("<Button-1>", lambda _e, k=key: command(k))
            widget.bind("<Enter>", self._hover_on)
            widget.bind("<Leave>", self._hover_off)

    def _paint(self, bg):
        for widget in self._parts:
            widget.configure(bg=bg)

    def _hover_on(self, _=None):
        if not self.active:
            self._paint(C["glass_hover"])

    def _hover_off(self, _=None):
        if not self.active:
            self._paint(C["sidebar"])

    def set_active(self, on):
        self.active = bool(on)
        self._paint(C["card"] if on else C["sidebar"])
        self.bar.configure(bg=C["accent"] if on else C["sidebar"])
        self.title_lbl.configure(fg=C["text"] if on else C["dim"])
        self.sub_lbl.configure(fg=C["dim"] if on else C["mute"])


class App(tk.Tk):
    def __init__(self, store=None):
        super().__init__()
        self.store = store or Store()
        self.look = dict(LOOK_DEFAULT)
        self.look.update(self.store.look())
        rebuild_theme(self.look)
        self.configure(bg=C["bg"])
        self.title("Trace Time · 时间痕迹")
        self.geometry("%dx%d" % (sp(1216), sp(812)))
        self.minsize(sp(1080), sp(720))
        style_ttk(self)
        self._nav = {}
        self._current = "timer"
        self._look_panel = None
        self._pomo_snap = None
        self._cal_day = None
        self._build()
        self.store.subscribe(self._on_data_changed)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._bind_keys()
        self.show_view("timer")
        self.update_summary()
        self.after(80, self._apply_window_material)
        self._modal_strikes = 0
        self.after(2000, self._modal_watchdog)

    # ------------------------------------------------------------------ 布局
    def _build(self):
        shell = tk.Frame(self, bg=C["bg"])
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=C["sidebar"], width=sp(200))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="TRACE TIME", font=F["h1"], bg=C["sidebar"],
                 fg=C["text"]).pack(anchor="w", padx=sp(20), pady=(sp(24), 0))
        tk.Label(sidebar, text="时间痕迹 · 你刚才在做什么", font=F["tiny"],
                 bg=C["sidebar"], fg=C["mute"]).pack(anchor="w", padx=sp(20), pady=(sp(4), sp(18)))

        for key, title, sub in NAV:
            btn = NavButton(sidebar, key, title, sub, self.show_view)
            btn.pack(fill="x", pady=sp(1))
            self._nav[key] = btn

        summary = tk.Frame(sidebar, bg=C["card2"])
        summary.pack(side="bottom", fill="x", padx=sp(12), pady=sp(12))
        inner = tk.Frame(summary, bg=C["card2"])
        inner.pack(fill="x", padx=sp(14), pady=sp(12))
        tk.Label(inner, text="今日", font=F["tiny"], bg=C["card2"], fg=C["mute"], anchor="w").pack(fill="x")
        self.sum_total = tk.Label(inner, text="0 分", font=F["h1"], bg=C["card2"],
                                  fg=C["green"], anchor="w")
        self.sum_total.pack(fill="x", pady=(sp(2), sp(4)))
        self.sum_detail = tk.Label(inner, text="番茄 0 · 待办 0", font=F["tiny"],
                                   bg=C["card2"], fg=C["dim"], anchor="w")
        self.sum_detail.pack(fill="x")

        look_btn = tk.Label(sidebar, text="◐  外观设置", font=F["small"], bg=C["sidebar"],
                            fg=C["dim"], cursor="hand2", anchor="w", padx=sp(20), pady=sp(8))
        look_btn.pack(side="bottom", fill="x")
        look_btn.bind("<Button-1>", lambda _e: self.open_look_panel())
        look_btn.bind("<Enter>", lambda _e: look_btn.configure(fg=C["text"]))
        look_btn.bind("<Leave>", lambda _e: look_btn.configure(fg=C["dim"]))

        content = tk.Frame(shell, bg=C["bg"])
        content.pack(side="left", fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self._content = content
        self.views = {}
        self._ensure_view("timer")

    # ------------------------------------------------------------------ 交互
    VIEW_CLASSES = {
        "timer": TimerView,
        "pomodoro": PomodoroView,
        "todo": TodoView,
        "calendar": CalendarView,
    }

    def _ensure_view(self, key):
        """视图按需创建：启动快，只有点到的页面才建控件。"""
        view = self.views.get(key)
        if view is not None:
            return view
        cls = self.VIEW_CLASSES[key]
        view = cls(self._content, self.store, self)
        view.grid(row=0, column=0, sticky="nsew")
        self.views[key] = view
        if key == "pomodoro" and self._pomo_snap:
            view.restore(self._pomo_snap)
        return view

    def show_view(self, key):
        if key not in self.VIEW_CLASSES:
            return
        view = self._ensure_view(key)
        self._current = key
        for name, btn in self._nav.items():
            btn.set_active(name == key)
        try:
            view.refresh()
        except Exception as exc:
            print("[app] 刷新视图失败:", exc)
        view.tkraise()

    def _on_data_changed(self):
        self.update_summary()
        view = self.views.get(self._current)
        if view is not None:
            try:
                view.refresh()
            except Exception as exc:
                print("[app] 刷新失败:", exc)

    def update_summary(self):
        day = today_str()
        stats = self.store.day_stats(day)
        self.sum_total.configure(text=fmt_span(stats["seconds"]))
        self.sum_detail.configure(text="番茄 %d · 待办 %d" % (stats["pomodoro"], self.store.pending_count()))

    # ------------------------------------------------------------------ 快捷键
    def _bind_keys(self):
        self.bind_all("<space>", self._on_space)
        self.bind_all("<Escape>", self._on_escape)
        for i, (key, _t, _s) in enumerate(NAV, start=1):
            self.bind_all("<Control-Key-%d>" % i, lambda _e, k=key: self.show_view(k))

    def _focus_is_input(self):
        focus = self.focus_get()
        if focus is None:
            return False
        if focus.winfo_toplevel() is not self:
            return True
        return focus.winfo_class() in ("Entry", "Text", "TEntry", "TCombobox", "Spinbox", "TSpinbox")

    def _on_space(self, _event=None):
        if self._focus_is_input():
            return
        if self._current == "timer":
            self.views["timer"]._primary_action()
        elif self._current == "pomodoro":
            self.views["pomodoro"]._toggle()

    def _on_escape(self, _event=None):
        if self._focus_is_input():
            return
        if self._current == "timer" and self.views["timer"].state != "idle":
            self.views["timer"]._finish()

    # ------------------------------------------------------------------ 外观
    def open_look_panel(self):
        geometry = None
        if self._look_panel is not None and self._look_panel.winfo_exists():
            geometry = self._look_panel.winfo_geometry()
            self._look_panel.destroy()
        self._look_panel = LookPanel(self, self, self.look, geometry)

    def set_look(self, **changes):
        need_rebuild = False
        for key, value in changes.items():
            if self.look.get(key) == value:
                continue
            if key in ("base", "accent", "radius"):
                need_rebuild = True
            self.look[key] = value
        self.store.set_look(self.look)
        if "alpha" in changes:
            self.apply_alpha()
        if "blur" in changes:
            self.apply_blur()
        if need_rebuild:
            self.rebuild_ui()

    def rebuild_ui(self):
        state = {
            "view": self._current,
            "timer": self.views["timer"].snapshot() if "timer" in self.views else None,
            "panel": None,
        }
        if "pomodoro" in self.views:
            self._pomo_snap = self.views["pomodoro"].snapshot()
        panel = self._look_panel
        if panel is not None and panel.winfo_exists():
            state["panel"] = panel.winfo_geometry()
            panel.destroy()
        self._look_panel = None
        rebuild_theme(self.look)
        style_ttk(self)
        self.configure(bg=C["bg"])
        for child in self.winfo_children():
            child.destroy()
        self.views.clear()
        self._nav.clear()
        self._build()
        if state["timer"]:
            self.views["timer"].restore(state["timer"])
        self.show_view(state["view"])
        self.update_summary()
        self.apply_alpha()
        self.apply_blur()
        self._apply_window_material()
        if state["panel"]:
            geometry = state["panel"]
            self.after(30, lambda g=geometry: self._reopen_panel(g))

    def _reopen_panel(self, geometry):
        if self._look_panel is None or not self._look_panel.winfo_exists():
            self._look_panel = LookPanel(self, self, self.look, geometry)

    def apply_alpha(self):
        try:
            self.attributes("-alpha", max(0.55, min(1.0, float(self.look.get("alpha", 0.96)))))
        except tk.TclError:
            pass

    def apply_blur(self):
        hwnd = winfx.hwnd_of(self)
        if not hwnd:
            return
        if self.look.get("blur", True):
            winfx.blur(hwnd, C["bg"], BLUR_STRENGTH)
        else:
            winfx.clear_blur(hwnd)

    def _apply_window_material(self):
        hwnd = winfx.hwnd_of(self)
        if not hwnd:
            return
        winfx.dark_titlebar(hwnd)
        winfx.round_window(hwnd)
        self.apply_alpha()
        self.apply_blur()

    # ------------------------------------------------------------------ 兜底
    def _modal_watchdog(self):
        """看门狗：万一有弹窗握着模态却看不见（主界面点不动、关不掉），把它清掉。

        连续两次（约 4 秒）都不可见才动手，避免误伤正常弹窗。
        """
        self.after(2000, self._modal_watchdog)
        try:
            holder = self.grab_current()
        except Exception:
            holder = None
        if not isinstance(holder, tk.Toplevel):
            self._modal_strikes = 0
            return
        try:
            if holder.winfo_exists() and not holder.winfo_viewable():
                self._modal_strikes += 1
                if self._modal_strikes >= 2:
                    self._modal_strikes = 0
                    try:
                        holder.grab_release()
                    except tk.TclError:
                        pass
                    holder.destroy()
                    self._log_to_startup("清理了一个不可见的模态弹窗")
            else:
                self._modal_strikes = 0
        except tk.TclError:
            self._modal_strikes = 0

    def _log_to_startup(self, message):
        try:
            path = self.store.path.parent / "startup.log"
            from datetime import datetime

            with path.open("a", encoding="utf-8") as fh:
                fh.write("%s  %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message))
        except Exception:
            pass

    # ------------------------------------------------------------------ 提醒
    def notify_user(self):
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            try:
                self.bell()
            except tk.TclError:
                pass
        self._flash_taskbar()

    def _flash_taskbar(self):
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = winfx.hwnd_of(self)

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("hwnd", wintypes.HWND),
                    ("dwFlags", wintypes.DWORD),
                    ("uCount", wintypes.UINT),
                    ("dwTimeout", wintypes.DWORD),
                ]

            info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x3 | 0xC, 6, 0)
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
        except Exception:
            pass

    # ------------------------------------------------------------------ 退出
    def _on_close(self):
        # 先清掉可能还开着的弹窗，免得它握着模态导致后面问询弹不出来
        for child in list(self.winfo_children()):
            if isinstance(child, tk.Toplevel):
                try:
                    child.grab_release()
                except tk.TclError:
                    pass
                try:
                    child.destroy()
                except tk.TclError:
                    pass
        timer = self.views["timer"]
        if timer.has_open_segment():
            choice = ask_choice(
                self, "还有一段没记录",
                "计时器还在走，这一段已经 %s。要先写下做了什么再退出吗？" % fmt_span(timer.elapsed()),
                [("记录并退出", C["accent"]), ("直接退出", C["card3"]), ("取消", C["card3"])],
            )
            if choice is None or choice == 2:
                return
            if choice == 0:
                timer._finish()
        self.store.save()
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
