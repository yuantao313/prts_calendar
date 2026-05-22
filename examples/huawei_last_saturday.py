"""
Example: 华为月末周六加班数据源。
规则：
  - 每个月的最后一个周六加班（全天事件）
  - 若该周六是法定节假日 → 跳过
  - 若该周六是调休工作日 → 跳过（政府安排优先）
  - 若加上本次加班会导致连续工作 7 天或以上 → 跳过
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta

import requests

from calpipe.base import DataSource

HOLIDAY_API = "https://timor.tech/api/holiday"
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "calendar-framework/1.0"})


def _last_day_of_month(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def _last_saturday(year: int, month: int) -> date:
    d = _last_day_of_month(year, month)
    while d.weekday() != 5:  # Saturday=5
        d -= timedelta(days=1)
    return d


class _HolidayCalendar:
    """Cached holiday + 调休 checker for a given year range."""

    def __init__(self, years: list[int]):
        self._holidays: set[str] = set()         # statutory holidays
        self._tiaoxiu_cache: dict[str, bool] = {}  # date_str → is_调休
        self._fetched = False
        self._years = years

    def ensure_fetched(self):
        if self._fetched:
            return
        for year in self._years:
            try:
                resp = _SESSION.get(f"{HOLIDAY_API}/year/{year}", timeout=10)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException:
                continue
            if data.get("code") != 0:
                continue
            for date_key, info in data.get("holiday", {}).items():
                if isinstance(info, dict) and info.get("holiday"):
                    self._holidays.add(info.get("date", f"{year}-{date_key}"))
        self._fetched = True

    def is_holiday(self, d: date) -> bool:
        self.ensure_fetched()
        return d.strftime("%Y-%m-%d") in self._holidays

    def is_tiaoxiu(self, d: date) -> bool:
        self.ensure_fetched()
        ds = d.strftime("%Y-%m-%d")
        if ds in self._tiaoxiu_cache:
            return self._tiaoxiu_cache[ds]
        try:
            resp = _SESSION.get(f"{HOLIDAY_API}/info/{ds}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            is_tx = data.get("type", {}).get("type") == 3
        except requests.RequestException:
            is_tx = False
        self._tiaoxiu_cache[ds] = is_tx
        return is_tx

    def is_rest_day(self, d: date) -> bool:
        """A day is rest if: statutory holiday, or (weekend and NOT 调休)."""
        if self.is_holiday(d):
            return True
        if d.weekday() >= 5:
            return not self.is_tiaoxiu(d)
        return False


class HuaweiLastSaturday(DataSource):
    def __init__(self, source_id: str, name: str, params: dict):
        super().__init__(source_id, name, params)
        years = params.get("years") or [datetime.now().year]
        if isinstance(years, int):
            years = [years]
        self._years = years
        self._cal = _HolidayCalendar(years)

    def get_events(self) -> list[dict]:
        events = []
        for year in self._years:
            for month in range(1, 13):
                sat = _last_saturday(year, month)
                if not self._should_work(sat):
                    continue
                month_name = sat.strftime("%Y年%-m月")
                events.append({
                    "title": f"{month_name}月末周六加班",
                    "start": datetime(sat.year, sat.month, sat.day, 9, 0),
                    "end": datetime(sat.year, sat.month, sat.day, 18, 0),
                    "description": f"{month_name}月末周六加班（华为）",
                    "url": "",
                })
        return events

    def _should_work(self, sat: date) -> bool:
        if self._cal.is_holiday(sat):
            return False
        if self._cal.is_tiaoxiu(sat):
            return False

        consecutive = 1  # this Saturday

        cursor = sat - timedelta(days=1)
        for _ in range(31):
            if self._cal.is_rest_day(cursor):
                break
            consecutive += 1
            if consecutive >= 7:
                return False
            cursor -= timedelta(days=1)

        cursor = sat + timedelta(days=1)
        for _ in range(31):
            if self._cal.is_rest_day(cursor):
                break
            consecutive += 1
            if consecutive >= 7:
                return False
            cursor += timedelta(days=1)

        return True
