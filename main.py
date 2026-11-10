"""Trace Time · 时间痕迹 —— 桌面端计时 / 番茄 / 待办 / 日历小工具。

用法：
    python main.py                      正常启动
    python main.py --where              只打印数据文件位置
    python main.py --data D:\\某目录     指定数据目录（或直接给 .json 路径）

打包成 exe 后用法完全一样，例如：
    TraceTime.exe --where
"""

import sys
import traceback


def parse_args(argv):
    data = None
    where = False
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg in ("-d", "--data") and index + 1 < len(argv):
            data = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--data="):
            data = arg.split("=", 1)[1]
            index += 1
            continue
        if arg in ("--where", "--data-path"):
            where = True
        index += 1
    return data, where


def single_instance_guard():
    """同一份数据只允许一个实例，避免两个窗口互相覆盖数据。"""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, "Local\\TraceTime.SingleInstance")
        already = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        return handle, not already
    except Exception:
        return None, True


def alert(message):
    print(message, file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("Trace Time", message)
        root.destroy()
    except Exception:
        pass


def main():
    data_arg, where = parse_args(sys.argv)
    try:
        from store import resolve_data_file

        data_path = resolve_data_file(data_arg)
    except Exception:
        data_path = None

    if where:
        print("数据文件:", data_path)
        return 0

    handle, first = single_instance_guard()
    if not first:
        alert("Trace Time 已经在运行了。\n\n"
              "同一份数据同时开两个窗口会互相覆盖，请使用已经打开的那个窗口。")
        return 0

    try:
        from app import App
        from store import Store

        App(store=Store(data_path)).mainloop()
    except Exception:
        detail = traceback.format_exc()
        alert("Trace Time 启动失败：\n\n" + detail[-1200:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
