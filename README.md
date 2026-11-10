# Trace Time · 时间痕迹

一个 Windows 桌面小工具，回答一个问题：**我这一天到底做了什么？**

- **计时器**：正计时，每次暂停都要交代「这两个暂停之间你做了什么」。
- **待办 + 日历**：任务清单，日历热力图回看每天的专注与待办。
- **番茄钟**：专注 / 短休 / 长休循环，每颗番茄结束同样记录内容。

纯 Python 标准库实现（tkinter），不装任何第三方库。

![计时器](screenshots/01-timer.png)

## 启动

双击 `run.bat`，或者：

```bat
cd /d D:\桌面\trace-time
python main.py
```

打包成 exe 后直接双击 `dist\TraceTime\TraceTime.exe`。**两种方式的界面和数据完全一致**（见下面「数据」）。

需要 Python 3.10+（本项目在 3.12 上开发）。

## 数据：bat 和 exe 共用同一份

数据统一放在：

```
%LOCALAPPDATA%\TraceTime\trace_time.json
```

也就是 `C:\Users\<你>\AppData\Local\TraceTime\trace_time.json`。

为什么不放在程序目录？因为 PyInstaller 打包后 `__file__` 会指向 `_internal`（或临时解包目录），
按程序目录找数据会导致 **bat 运行写一份、exe 运行又写另一份**。放到用户目录后，
不管怎么启动，读写的都是同一个文件。

配套的几个措施：

- **旧数据自动合并**：第一次启动会把旧位置的数据（项目的 `data\`、exe 的 `_internal\data\` 等）
  按记录 id 并进主文件，不会丢。并过哪些文件记在文件的 `merged_from` 里，不会重复合并。
- **启动日志**：`%LOCALAPPDATA%\TraceTime\startup.log` 每次启动记一行（启动方式 / 数据路径 / 记录数），
  怀疑数据不对时先看这里。
- **单实例保护**：同一份数据只允许开一个窗口，重复启动会提示「已经在运行」，不会两个窗口互相覆盖。
- **界面里能看**：左下角 `◐ 外观设置` 底部显示当前数据文件路径，旁边有「打开数据文件夹」。

想看数据到底在哪（命令行）：

```bat
python main.py --where
dist\TraceTime\TraceTime.exe --where
```

想换个位置（两种启动方式都读同一个）：

```bat
python main.py --data D:\我的数据
python main.py --data D:\我的数据\trace.json
set TRACE_TIME_DATA=D:\我的数据\trace_time.json
```

想要便携模式（数据跟着程序走）：在 `TraceTime.exe`（或 `main.py`）旁边放一个空的 `portable.txt`，
数据就存到程序目录下的 `data\`。

旧位置的 `data\trace_time.json` 合并后可以留着当备份，也可以直接删。

## 界面

- 圆角玻璃风：面板是圆角 + 高亮描边的玻璃块，按钮/标签也是圆角。
- 真 DPI 感知：进程声明 Per-Monitor V2，所有尺寸按屏幕 DPI 等比放大（150% 缩放下按 1.5 倍布局），
  字体用像素大小而不是点，字高落在整数像素上——不再被 Windows 位图拉伸，所以文字清晰。
- 窗口材质：Windows 11 圆角窗口 + 深色标题栏 + 毛玻璃模糊背景。
- 点左下角 **◐ 外观设置**：底色（深夜 / 石墨 / 暗紫 / 深海）、强调色（6 种）、
  窗口透明度（55%–100%）、圆角大小、毛玻璃开关，改完立刻生效并记住。

![外观设置](screenshots/05-look.png)

## 三个核心功能

### 1. 计时器 —— 暂停时记录

- 点「开始」，正计时一直走；点「暂停并记录」（或空格）弹出输入框：
  「这 37 分，你做了什么？」填一句、可选归类（开发 / 会议 / 沟通…）。
- 「继续下一段」开始新的一段；「结束并记录」收工。
- 每段带时间段、时长、内容进入右侧时间线，全天累计显示在下方。

### 2. 待办 + 日历

- 待办：输入框回车即添加，可定优先级 / 截止日期 / 标签；勾圆点完成，双击标题修改；
  支持 全部 / 未完成 / 今日 / 已完成 筛选，逾期日期标红。
- 日历：月视图热力图（格子越深 = 那天专注越久），橙点 = 当天未完成待办，绿点 = 番茄；
  点任意一天，右侧显示那天的待办、番茄数、总时长和完整时间线，也能直接给那天加待办。

![日历](screenshots/04-calendar.png)

### 3. 番茄钟

- 圆环进度，专注 / 短休 / 长休自动循环，时长与长休间隔可改。
- 每颗番茄结束时问「这段时间做了什么」并计入今日统计。
- 阶段结束响提示音 + 任务栏闪烁（窗口最小化时会自动恢复，好让你看见）。

关于阶段结束时的弹窗，做了几层保险，避免「弹窗卡住、界面点不动也关不掉」：

- 先推进到下一阶段（计时继续），再另起一个空闲回合弹窗，**不会卡在计时回调里**；
- 弹窗挂在主窗口下、并确认真的显示出来才抓模态，抓不到就不抓（主界面永远能点）；
- 弹窗被遮挡或不可见超过约 4 秒会被自动清理（清理动作写进 `startup.log`）；
- 上一条还没填完时不会再叠一个弹窗，数据先记下来、内容留空，不丢记录。

![番茄钟](screenshots/02-pomodoro.png)

## 快捷键

| 按键 | 作用 |
| --- | --- |
| 空格 | 开始 / 暂停并记录（番茄钟页则是开始 / 暂停） |
| Esc | 结束并记录当前段 |
| Ctrl+1 / 2 / 3 / 4 | 切到 计时器 / 番茄钟 / 待办 / 日历 |
| Ctrl+Enter | 记录弹窗里保存 |
| Esc | 记录弹窗里跳过 |

## 打包成 exe

双击 `build.bat`，或者：

```bat
pip install pyinstaller
python -m PyInstaller --noconfirm --clean --noconsole --name TraceTime main.py
```

产物：`dist\TraceTime\TraceTime.exe`。数据仍然统一存在 `%LOCALAPPDATA%\TraceTime\`。

## 目录结构

```
main.py            启动入口（单实例保护、--data / --where）
app.py             主窗口、左侧导航、按需创建视图、快捷键、提醒
theme.py           配色 / 字体 / DPI 缩放（所有视觉令牌）
winfx.py           窗口材质：深色标题栏、圆角窗口、毛玻璃
look.py            外观设置面板（含数据文件位置）
widgets.py         圆角玻璃面板、圆角按钮、胶囊、滑块、滚动容器等
dialog.py          记录弹窗、待办编辑弹窗、确认框
store.py           数据位置解析、读写、旧数据合并、统计
view_timer.py      计时器视图
view_pomodoro.py   番茄钟视图
view_todo.py       待办视图
view_calendar.py   日历视图
run.bat            源码方式启动
build.bat          打包 exe
screenshots/       界面截图
```
