"""
Example: 公司发薪日数据源。
根据配置的发薪日和策略（提前/延后/不调整）计算实际发放日。
用法：在 config.json 中设置 "script": "examples/company_payday.py"
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta

import requests

from calpipe.base import DataSource

HOLIDAY_API_BASE = "https://timor.tech/api/holiday"
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "calendar-framework/1.0"})


class _HolidayChecker:
    """Lightweight holiday checker used by this source."""

    def __init__(self, years: list[int]):
        self._holiday_dates: set[str] = set()
        for year in years:
            try:
                resp = _SESSION.get(f"{HOLIDAY_API_BASE}/year/{year}", timeout=10)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException:
                continue
            if data.get("code") != 0:
                continue
            for date_key, info in data.get("holiday", {}).items():
                if isinstance(info, dict) and info.get("holiday"):
                    self._holiday_dates.add(info.get("date", f"{year}-{date_key}"))

    def is_rest_day(self, d: date) -> bool:
        if d.strftime("%Y-%m-%d") in self._holiday_dates:
            return True
        if d.weekday() >= 5:
            return True
        return False


class CompanyPayday(DataSource):
    SUPPORTED_STRATEGIES = ("advance", "delay", "none")

    def __init__(self, source_id: str, name: str, params: dict):
        super().__init__(source_id, name, params)
        self.pay_day = params.get("pay_day", 15)
        self.strategy = params.get("strategy", "advance")
        self._years = params.get("years") or [datetime.now().year, datetime.now().year + 1]

        if self.pay_day < 1 or self.pay_day > 28:
            raise ValueError(f"pay_day 必须在 1-28 之间，得到: {self.pay_day}")
        if self.strategy not in self.SUPPORTED_STRATEGIES:
            raise ValueError(f"strategy 必须是 {self.SUPPORTED_STRATEGIES} 之一")

        self._checker = _HolidayChecker(self._years)

    def get_events(self) -> list[dict]:
        events = []
        for year in self._years:
            for month in range(1, 13):
                actual = self._calc(year, month)
                month_name = actual.strftime("%Y年%-m月")
                desc_parts = [f"{month_name}发薪日（每月 {self.pay_day} 日）"]
                if self.strategy == "advance":
                    desc_parts.append("如遇休息日，提前至最近的工作日")
                elif self.strategy == "delay":
                    desc_parts.append("如遇休息日，延后至最近的工作日")
                elif self.strategy == "none":
                    desc_parts.append("不因休息日调整")
                events.append({
                    "title": f"{month_name}发薪日",
                    "start": datetime(actual.year, actual.month, actual.day),
                    "end": datetime(actual.year, actual.month, actual.day) + timedelta(days=1),
                    "description": "\n".join(desc_parts),
                    "url": "",
                })
        return events

    def _calc(self, year: int, month: int) -> date:
        max_day = monthrange(year, month)[1]
        candidate = date(year, month, min(self.pay_day, max_day))
        if self.strategy == "none":
            return candidate
        direction = -1 if self.strategy == "advance" else 1
        for _ in range(31):
            if not self._checker.is_rest_day(candidate):
                return candidate
            candidate += timedelta(days=direction)
        return candidate
