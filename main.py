"""Trace Time · 时间痕迹 —— 桌面端计时 / 番茄 / 待办 / 日历小工具。

启动：python main.py（或双击 run.bat）
"""

import sys
import traceback


def main():
    try:
        from app import App

        App().mainloop()
    except Exception:
        detail = traceback.format_exc()
        print(detail, file=sys.stderr)
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Trace Time 启动失败", detail[-1500:])
            root.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
