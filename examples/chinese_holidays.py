"""
Example: 中国法定节假日数据源。
从 timor.tech API 获取节假日，继承 DataSource 生成 ICS。
用法：在 config.json 中设置 "script": "examples/chinese_holidays.py"
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import requests

from calpipe.base import DataSource

HOLIDAY_API_BASE = "https://timor.tech/api/holiday"
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "calendar-framework/1.0"})


class ChineseHolidayChecker:
    """Shared utility for checking if a date is a rest day."""

    def __init__(self, years: list[int]):
        self._holiday_dates: set[str] = set()
        self._rest_info: dict[str, dict] = {}
        for year in years:
            self._fetch_year(year)

    def _fetch_year(self, year: int):
        try:
            resp = _SESSION.get(f"{HOLIDAY_API_BASE}/year/{year}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            return
        if data.get("code") != 0:
            return
        for date_key, info in data.get("holiday", {}).items():
            if isinstance(info, dict) and info.get("holiday"):
                full_date = info.get("date", f"{year}-{date_key}")
                self._holiday_dates.add(full_date)
                self._rest_info[full_date] = {"name": info.get("name", ""), "rest": info.get("rest", "")}

    def is_rest_day(self, d: date | datetime) -> bool:
        if isinstance(d, datetime):
            d = d.date()
        if d.strftime("%Y-%m-%d") in self._holiday_dates:
            return True
        if d.weekday() >= 5:
            return True
        return False

    def get_info(self, d: date | datetime) -> dict | None:
        if isinstance(d, datetime):
            d = d.date()
        return self._rest_info.get(d.strftime("%Y-%m-%d"))


class ChineseHolidaysSource(DataSource):
    def __init__(self, source_id: str, name: str, params: dict):
        super().__init__(source_id, name, params)
        years = params.get("years")
        if years is None:
            years = [datetime.now().year, datetime.now().year + 1]
        self.years = years
        self.checker = ChineseHolidayChecker(years)

    def get_events(self) -> list[dict]:
        events = []
        for year in self.years:
            for month in range(1, 13):
                try:
                    resp = _SESSION.get(f"{HOLIDAY_API_BASE}/year/{year}?month={month}", timeout=10)
                    resp.raise_for_status()
                    data = resp.json()
                except requests.RequestException:
                    continue
                if data.get("code") != 0:
                    continue
                for date_key, info in data.get("holiday", {}).items():
                    if not isinstance(info, dict) or not info.get("holiday"):
                        continue
                    full_date = info.get("date", f"{year}-{date_key}")
                    holiday_name = info.get("name", "节假日")
                    try:
                        start = datetime.strptime(full_date, "%Y-%m-%d")
                    except ValueError:
                        continue
                    desc = f"{holiday_name} 法定节假日"
                    if info.get("rest"):
                        desc += f"\n假期安排: {info['rest']}"
                    events.append({
                        "title": holiday_name,
                        "start": start,
                        "end": start + timedelta(days=1),
                        "description": desc,
                        "url": "",
                    })
        return events
