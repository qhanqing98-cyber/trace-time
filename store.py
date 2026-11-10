"""数据层：待办、时间段记录、设置的读写、统计与变更通知。

数据文件位置的规则（这也是"bat 运行 vs exe 运行数据不一致"的修复点）：

1. `--data 路径` 或环境变量 `TRACE_TIME_DATA` 显式指定时，用指定的；
2. 程序目录里有 `portable.txt` → 便携模式，数据放程序目录下的 `data/`；
3. 其余情况 → `%LOCALAPPDATA%\\TraceTime\\trace_time.json`。
   注意：**默认不放在程序目录**，因为 PyInstaller 打包后 `__file__` 会指向
   `_internal`（一次性/随包目录），bat 运行和 exe 运行就会各存一份。
   放到用户目录后，两种启动方式天然共用同一份数据。

旧版本的散落数据（项目的 data/、exe 的 _internal/data/ 等）会在第一次启动时
按 id 合并进主文件，合并过哪些文件记在 `merged_from` 里，不会重复合并。
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

APP_NAME = "TraceTime"

SOURCE_DIR = Path(__file__).resolve().parent


def program_dir() -> Path:
    """exe 所在目录（打包后）；源码运行时是项目目录。"""
    if getattr(sys, "frozen", False):
        try:
            return Path(sys.executable).resolve().parent
        except OSError:
            pass
    return SOURCE_DIR


def user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ("." + APP_NAME.lower())


def _writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _as_data_file(value) -> Path:
    """允许传文件路径或目录。"""
    path = Path(value).expanduser()
    if path.suffix.lower() == ".json":
        return path
    return path / "data" / "trace_time.json"


def resolve_data_file(override=None, portable=None) -> Path:
    """算出这次该用哪个数据文件。"""
    explicit = override or os.environ.get("TRACE_TIME_DATA") or os.environ.get("TRACE_TIME_DATA_DIR")
    if explicit:
        return _as_data_file(explicit)

    prog = program_dir()
    if portable is None:
        portable = (prog / "portable.txt").exists()
    if portable:
        return prog / "data" / "trace_time.json"

    home = user_data_dir()
    if _writable(home):
        return home / "trace_time.json"
    return prog / "data" / "trace_time.json"


DATA_FILE = resolve_data_file()
DATA_DIR = DATA_FILE.parent


def legacy_data_files(canonical: Path):
    """可能藏着旧数据的文件（按 id 合并用）。"""
    candidates = [
        SOURCE_DIR / "data" / "trace_time.json",
        program_dir() / "data" / "trace_time.json",
        program_dir() / "_internal" / "data" / "trace_time.json",
        Path.cwd() / "data" / "trace_time.json",
        user_data_dir() / "data" / "trace_time.json",
    ]
    try:
        canonical_key = str(canonical.resolve()).lower()
    except OSError:
        canonical_key = str(canonical).lower()
    seen, out = set(), []
    for path in candidates:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()
        if key == canonical_key or key in seen:
            continue
        seen.add(key)
        try:
            if path.is_file():
                out.append(path)
        except OSError:
            continue
    return out


PRIORITIES = ("high", "mid", "low")
PRIORITY_LABEL = {"high": "高", "mid": "中", "low": "低"}
PRIORITY_COLOR = {"high": "#ff6b6b", "mid": "#ffa94d", "low": "#5b8cff"}
PRIORITY_ORDER = {"high": 0, "mid": 1, "low": 2}

DEFAULT_SETTINGS = {
    "pomodoro": {
        "focus": 25,
        "short": 5,
        "long": 15,
        "long_every": 4,
        "auto_next": True,
        "sound": True,
    },
    "tags": ["开发", "会议", "沟通", "学习", "杂事", "休息"],
    "look": {"base": "night", "accent": "blue", "alpha": 0.96, "blur": True, "radius": 20},
}


def today_str(d=None):
    return (d or date.today()).isoformat()


def fmt_clock(seconds):
    """00:12 / 1:02:33"""
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)


def fmt_span(seconds):
    """人类可读：2 小时 5 分 / 38 分 / 45 秒"""
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h and m:
        return "%d 小时 %d 分" % (h, m)
    if h:
        return "%d 小时" % h
    if m:
        return "%d 分" % m
    return "%d 秒" % s


class Store:
    def __init__(self, path=None, migrate=True):
        self.path = Path(path) if path else DATA_FILE
        self._listeners = []
        self.fresh = not self.path.exists()
        self.data = self._load()
        if migrate:
            self._merge_legacy()
        self._write_startup_log()

    @property
    def data_path(self):
        return self.path

    # ------------------------------------------------------------------ 基础
    @staticmethod
    def _default():
        return {"version": 1, "todos": [], "segments": [], "settings": deepcopy(DEFAULT_SETTINGS)}

    def _load(self):
        data = self._default()
        if not self.path.exists():
            return data
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            try:
                self.path.replace(self.path.with_name(self.path.name + ".broken"))
            except OSError:
                pass
            return data
        if not isinstance(raw, dict):
            return data
        for key in ("todos", "segments"):
            if isinstance(raw.get(key), list):
                data[key] = [r for r in raw[key] if isinstance(r, dict)]
        if isinstance(raw.get("merged_from"), list):
            data["merged_from"] = [x for x in raw["merged_from"] if isinstance(x, str)]
        settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
        for key, val in DEFAULT_SETTINGS.items():
            if isinstance(val, dict):
                merged = deepcopy(val)
                src = settings.get(key)
                if isinstance(src, dict):
                    merged.update({k: v for k, v in src.items() if k in val})
                data["settings"][key] = merged
            else:
                data["settings"][key] = settings.get(key, deepcopy(val))
        data["version"] = raw.get("version", 1)
        return data

    def _merge_legacy(self):
        """把旧版本散落在别处的数据并进来（按 id 去重，只并一次）。"""
        done = self.data.setdefault("merged_from", [])
        changed = False

        if self.fresh:
            # 第一次用新位置：优先继承数据最多的那份的偏好设置
            best, best_score = None, -1
            for path in legacy_data_files(self.path):
                raw = self._read_json(path)
                if not raw:
                    continue
                score = len(raw.get("segments") or []) + len(raw.get("todos") or [])
                if score > best_score:
                    best, best_score = raw, score
            if best:
                self._adopt_settings(best.get("settings"))
                changed = True

        for path in legacy_data_files(self.path):
            key = str(path)
            if key in done:
                continue
            raw = self._read_json(path)
            done.append(key)
            changed = True
            if not raw:
                continue
            for field in ("segments", "todos"):
                existing = {rec.get("id") for rec in self.data.get(field) or [] if isinstance(rec, dict)}
                for rec in raw.get(field) or []:
                    if isinstance(rec, dict) and rec.get("id") and rec.get("id") not in existing:
                        self.data.setdefault(field, []).append(rec)
                        existing.add(rec.get("id"))
        if changed:
            self.save()

    @staticmethod
    def _read_json(path):
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else None
        except Exception:
            return None

    def _adopt_settings(self, settings):
        if not isinstance(settings, dict):
            return
        for key, default in DEFAULT_SETTINGS.items():
            src = settings.get(key)
            if isinstance(default, dict) and isinstance(src, dict):
                target = self.data["settings"][key]
                target.update({k: v for k, v in src.items() if k in default})
            elif src is not None:
                self.data["settings"][key] = src

    def _write_startup_log(self):
        """记一行启动日志，方便确认两种启动方式到底用的哪个数据文件。"""
        try:
            log = self.path.parent / "startup.log"
            if log.exists() and log.stat().st_size > 128 * 1024:
                log.unlink()
            mode = "exe(打包)" if getattr(sys, "frozen", False) else "源码"
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with log.open("a", encoding="utf-8") as fh:
                fh.write("%s  启动=%s  数据=%s  记录=%d 待办=%d\n"
                         % (stamp, mode, self.path, len(self.data.get("segments") or []),
                            len(self.data.get("todos") or [])))
        except OSError:
            pass

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            print("[store] 保存失败:", exc)

    def subscribe(self, fn):
        self._listeners.append(fn)

    def notify(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception as exc:  # 界面刷新失败不应该影响数据
                print("[store] 刷新失败:", exc)

    # ------------------------------------------------------------------ 待办
    def todos(self):
        return self.data["todos"]

    def sorted_todos(self, rows):
        return sorted(
            rows,
            key=lambda r: (
                1 if r.get("done") else 0,
                r.get("due") or "9999-99-99",
                PRIORITY_ORDER.get(r.get("priority"), 1),
                r.get("created") or "",
            ),
        )

    def add_todo(self, title, due="", priority="mid", tag="", est=0):
        title = (title or "").strip()
        if not title:
            return None
        rec = {
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "done": False,
            "due": due or "",
            "priority": priority if priority in PRIORITY_LABEL else "mid",
            "tag": (tag or "").strip(),
            "est": int(est or 0),
            "created": datetime.now().isoformat(timespec="seconds"),
            "done_at": "",
        }
        self.data["todos"].append(rec)
        self.save()
        self.notify()
        return rec

    def update_todo(self, tid, **fields):
        for rec in self.todos():
            if rec.get("id") == tid:
                rec.update({k: v for k, v in fields.items() if k in rec})
                self.save()
                self.notify()
                return rec
        return None

    def toggle_todo(self, tid):
        for rec in self.todos():
            if rec.get("id") == tid:
                rec["done"] = not rec.get("done")
                rec["done_at"] = datetime.now().isoformat(timespec="seconds") if rec["done"] else ""
                self.save()
                self.notify()
                return rec["done"]
        return None

    def delete_todo(self, tid):
        before = len(self.data["todos"])
        self.data["todos"] = [r for r in self.todos() if r.get("id") != tid]
        if len(self.data["todos"]) != before:
            self.save()
            self.notify()

    def clear_done(self):
        before = len(self.data["todos"])
        self.data["todos"] = [r for r in self.todos() if not r.get("done")]
        removed = before - len(self.data["todos"])
        if removed:
            self.save()
            self.notify()
        return removed

    def todos_for(self, day):
        return [r for r in self.todos() if r.get("due") == day]

    def pending_count(self, day=None):
        rows = self.todos_for(day) if day else self.todos()
        return sum(1 for r in rows if not r.get("done"))

    # ------------------------------------------------------------ 时间段记录
    def add_segment(self, start, end, note="", tag="", source="timer"):
        seconds = int((end - start).total_seconds())
        if seconds < 1:
            seconds = 1
        rec = {
            "id": uuid.uuid4().hex[:12],
            "date": start.date().isoformat(),
            "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"),
            "seconds": seconds,
            "note": (note or "").strip(),
            "tag": (tag or "").strip(),
            "source": source,
            "ts": start.isoformat(timespec="seconds"),
        }
        self.data["segments"].append(rec)
        self.save()
        self.notify()
        return rec

    def segments(self, day=None):
        segs = self.data["segments"]
        if day is None:
            return list(segs)
        return [s for s in segs if s.get("date") == day]

    def day_stats(self, day):
        segs = self.segments(day)
        total = sum(int(s.get("seconds", 0)) for s in segs)
        pomo = sum(1 for s in segs if s.get("source") == "pomodoro")
        return {"seconds": total, "count": len(segs), "pomodoro": pomo}

    def month_stats(self, year=None, month=None):
        out = {}
        for s in self.data["segments"]:
            day = s.get("date")
            if not day:
                continue
            if year and month:
                if not day.startswith("%04d-%02d" % (year, month)):
                    continue
            st = out.setdefault(day, {"seconds": 0, "count": 0, "pomodoro": 0})
            st["seconds"] += int(s.get("seconds", 0))
            st["count"] += 1
            if s.get("source") == "pomodoro":
                st["pomodoro"] += 1
        return out

    def total_seconds(self, day=None, source=None):
        rows = self.segments(day)
        if source:
            rows = [s for s in rows if s.get("source") == source]
        return sum(int(s.get("seconds", 0)) for s in rows)

    def pomodoro_count(self, day=None):
        rows = self.segments(day)
        return sum(1 for s in rows if s.get("source") == "pomodoro")

    def delete_segment(self, sid):
        before = len(self.data["segments"])
        self.data["segments"] = [s for s in self.segments() if s.get("id") != sid]
        if len(self.data["segments"]) != before:
            self.save()
            self.notify()

    def recent_notes(self, limit=5):
        seen, out = set(), []
        for s in reversed(self.data["segments"]):
            note = (s.get("note") or "").strip()
            if note and note not in seen:
                seen.add(note)
                out.append(note)
            if len(out) >= limit:
                break
        return out

    # ---------------------------------------------------------------- 设置项
    def settings(self):
        return self.data["settings"]

    def pomo(self):
        return self.data["settings"]["pomodoro"]

    def set_pomo(self, key, value):
        pomo = self.data["settings"]["pomodoro"]
        if key in pomo:
            pomo[key] = value
            self.save()

    def tags(self):
        return list(self.data["settings"].get("tags") or DEFAULT_SETTINGS["tags"])

    def look(self):
        """外观设置：底色 / 强调色 / 透明度 / 毛玻璃 / 圆角。"""
        stored = self.data["settings"].get("look")
        base = dict(DEFAULT_SETTINGS["look"])
        if isinstance(stored, dict):
            base.update({k: v for k, v in stored.items() if k in base})
        return base

    def set_look(self, look):
        current = self.look()
        current.update({k: v for k, v in dict(look).items() if k in current})
        self.data["settings"]["look"] = current
        self.save()
