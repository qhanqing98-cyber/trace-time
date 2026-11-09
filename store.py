"""数据层：待办、时间段记录、设置的读写、统计与变更通知。

所有数据都存在 data/trace_time.json 里，纯文本、可备份、可手工编辑。
"""

from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_FILE = DATA_DIR / "trace_time.json"

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
    def __init__(self, path=None):
        self.path = Path(path) if path else DATA_FILE
        self._listeners = []
        self.data = self._load()

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
