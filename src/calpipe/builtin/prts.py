"""Built-in: 明日方舟 PRTS Wiki 数据源。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

import requests
from bs4 import BeautifulSoup

from calpipe.base import DataSource

PRTS_API_URL = "https://prts.wiki/api.php"
PRTS_MOBILE_API_URL = "https://m.prts.wiki/api.php"

TIME_RANGE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})\s*~\s*(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})")
TIME_SINGLE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})")

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})


def _fetch_html(api_url: str, page_title: str, mobileformat: bool = False) -> str:
    params = {"action": "parse", "format": "json", "page": page_title}
    if mobileformat:
        params["mobileformat"] = "true"
    r = _SESSION.get(api_url.rstrip("/"), params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise ValueError(f"API 错误: {data['error'].get('info', data['error'])}")
    if "parse" not in data or "text" not in data["parse"]:
        raise ValueError("API 未返回 parse.text")
    return data["parse"]["text"]["*"]


def _cell_text(cell) -> str:
    if cell is None:
        return ""
    return " ".join(cell.get_text(separator=" ", strip=True).split())


def _op_names(cell) -> list[str]:
    if cell is None:
        return []
    names, seen = [], set()
    for a in cell.find_all("a", href=True):
        href = a.get("href", "")
        if not href.startswith("/w/"):
            continue
        name = a.get("title", "").strip()
        if not name:
            name = unquote(href.rstrip("/").split("/")[-1], encoding="utf-8").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _comment_notes(cell) -> list[str]:
    if cell is None:
        return []
    return [s.strip() for s in re.findall(r"※[^※]+", _cell_text(cell)) if s.strip()]


def _parse_time_range(s: str) -> tuple[datetime | None, datetime | None]:
    m = TIME_RANGE_PATTERN.search(s.replace("\n", " ").replace("\r", " "))
    if not m:
        return None, None
    try:
        return (
            datetime.strptime(m.group(1).strip(), "%Y-%m-%d %H:%M"),
            datetime.strptime(m.group(2).strip(), "%Y-%m-%d %H:%M"),
        )
    except ValueError:
        return None, None


def _parse_single_time(s: str) -> tuple[datetime | None, datetime | None]:
    m = TIME_SINGLE_PATTERN.search(s.replace("\n", " ").replace("\r", " "))
    if not m:
        return None, None
    try:
        start = datetime.strptime(m.group(1).strip(), "%Y-%m-%d %H:%M")
        return start, start + timedelta(hours=1)
    except ValueError:
        return None, None


def _page_name(href: str) -> str:
    if not href.startswith("/w/"):
        return ""
    path = href.split("/w/", 1)[-1].strip("/")
    return unquote(path, encoding="utf-8").split("/")[-1].strip() if path else ""


def _title_and_url(cell) -> tuple[str, str]:
    title, wiki_path = "", ""
    for a in cell.find_all("a", href=True):
        href = a.get("href", "")
        if not href.startswith("/w/"):
            continue
        t = _page_name(href)
        if not t:
            t = _cell_text(a).strip() or a.get("title", "").strip()
        if len(t) > len(title):
            title, wiki_path = t, href
    if not title:
        title = _cell_text(cell)
    if not title and wiki_path:
        title = _page_name(wiki_path)
    return title.strip(), ("https://prts.wiki" + wiki_path) if wiki_path else ""


def _parse_pool_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events, seen = [], set()
    for table in soup.find_all("table", class_=re.compile(r"wikitable")):
        rows = table.find_all("tr")
        if not rows:
            continue
        if "开启时间" not in _cell_text(rows[0]) or "寻访页面" not in _cell_text(rows[0]):
            continue
        hdr = rows[0].find_all(["th", "td"])
        col_page = col_time = col_6 = col_5 = None
        for i, c in enumerate(hdr):
            t = _cell_text(c)
            if "寻访页面" in t:
                col_page = i
            if "开启时间" in t:
                col_time = i
            if "6" in t and ("星" in t or "★" in t):
                col_6 = i
            if "5" in t and ("星" in t or "★" in t):
                col_5 = i
        if col_page is None or col_time is None:
            continue
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(col_page, col_time):
                continue
            title, wiki_url = _title_and_url(cells[col_page])
            if not title:
                continue
            start, end = _parse_time_range(_cell_text(cells[col_time]))
            if start is None or end is None:
                continue
            desc_parts = []
            if col_6 is not None and len(cells) > col_6:
                s6 = _op_names(cells[col_6])
                if s6:
                    desc_parts.append("6★: " + "、".join(s6))
                desc_parts.extend(_comment_notes(cells[col_6]))
            if col_5 is not None and len(cells) > col_5:
                s5 = _op_names(cells[col_5])
                if s5:
                    desc_parts.append("5★&4★: " + "、".join(s5))
                desc_parts.extend(_comment_notes(cells[col_5]))
            key = (title, start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            events.append({
                "title": title, "start": start, "end": end,
                "description": "\n".join(desc_parts).strip(),
                "url": wiki_url,
            })
    return events


def _parse_activity_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events, seen = [], set()
    for table in soup.find_all("table", class_=re.compile(r"wikitable")):
        rows = table.find_all("tr")
        if not rows:
            continue
        if "活动开始时间" not in _cell_text(rows[0]) or "活动页面" not in _cell_text(rows[0]):
            continue
        hdr = rows[0].find_all(["th", "td"])
        col_time = col_page = col_desc = None
        for i, c in enumerate(hdr):
            t = _cell_text(c)
            if "活动开始时间" in t:
                col_time = i
            if "活动页面" in t:
                col_page = i
            if "活动分类" in t:
                col_desc = i
        if col_time is None or col_page is None:
            continue
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(col_time, col_page):
                continue
            title, wiki_url = _title_and_url(cells[col_page])
            if not title:
                continue
            start, end = _parse_single_time(_cell_text(cells[col_time]))
            if start is None:
                continue
            desc = _cell_text(cells[col_desc]).strip() if col_desc is not None and len(cells) > col_desc else ""
            key = (title, start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            events.append({
                "title": title, "start": start, "end": end,
                "description": desc, "url": wiki_url,
            })
    return events


class PrtsWikiSource(DataSource):
    def __init__(self, source_id: str, name: str, params: dict):
        super().__init__(source_id, name, params)
        self.page_title = params["page_title"]
        self.api_url = params.get("api_url", PRTS_API_URL)
        self.mobileformat = params.get("mobileformat", False)
        self.append_year = params.get("append_year", False)
        self._years = params.get("years") or []
        self.parse_mode = params.get("parse_mode", "pool")

    def get_events(self) -> list[dict]:
        if self.append_year and self._years:
            all_events = []
            for year in self._years:
                try:
                    html = _fetch_html(self.api_url, f"{self.page_title}/{year}", self.mobileformat)
                    all_events.extend(self._parse(html))
                except (ValueError, requests.RequestException) as e:
                    print(f"  → {self.page_title}/{year} 获取失败: {e}")
            seen = set()
            events = []
            for ev in all_events:
                key = (ev["title"], ev["start"].isoformat())
                if key not in seen:
                    seen.add(key)
                    events.append(ev)
        else:
            html = _fetch_html(self.api_url, self.page_title, self.mobileformat)
            events = self._parse(html)

        default_wiki = "https://prts.wiki/w/" + quote(self.page_title, safe="/")
        for ev in events:
            ev.setdefault("url", default_wiki)
        return events

    def _parse(self, html: str) -> list[dict]:
        return _parse_activity_table(html) if self.parse_mode == "activity" else _parse_pool_table(html)
