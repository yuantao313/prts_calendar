"""
PRTS 日历：通过 MediaWiki API 获取页面 HTML，解析表格后按年份生成 ICS。
数据源在 sources 中配置；支持卡池（寻访页面+开启时间）与活动一览（活动页面+活动开始时间）。
"""

import hashlib
import os
import re
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("请先安装依赖: pip install beautifulsoup4")

try:
    from icalendar import Calendar, Event
except ImportError:
    raise SystemExit("请先安装依赖: pip install icalendar")

# 时间范围：2026-02-10 12:00~2026-02-24 03:59
TIME_RANGE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})\s*~\s*(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})"
)
# 单时刻：2026-02-24 16:00（活动开始时间）
TIME_SINGLE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})


def fetch_page_via_api(api_url: str, page_title: str, mobileformat: bool = False) -> str:
    """通过 MediaWiki action=parse API 获取页面 HTML。"""
    params = {"action": "parse", "format": "json", "page": page_title}
    if mobileformat:
        params["mobileformat"] = "true"
    url = api_url.rstrip("/")
    r = SESSION.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise ValueError(f"API 错误: {data['error'].get('info', data['error'])}")
    if "parse" not in data or "text" not in data["parse"]:
        raise ValueError("API 未返回 parse.text")
    return data["parse"]["text"]["*"]


def _cell_text(cell) -> str:
    """提取单元格纯文本，合并空白。"""
    if cell is None:
        return ""
    text = cell.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def _operator_names_from_cell(cell) -> list[str]:
    """
    从单元格中提取干员名：只认指向 /w/ 的 wiki 链接。
    优先用 <a> 的 title，否则用 href 路径最后一段（URL 解码）。
    忽略链接内的图标文字（如「限兑兑」）。
    """
    if cell is None:
        return []
    names = []
    seen = set()
    for a in cell.find_all("a", href=True):
        href = a.get("href", "")
        if not href.startswith("/w/"):
            continue
        name = a.get("title", "").strip()
        if not name:
            # /w/干员名 或 /w/URL编码名
            segment = href.rstrip("/").split("/")[-1]
            name = unquote(segment, encoding="utf-8")
        name = name.strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _comment_notes_from_cell(cell) -> list[str]:
    """
    从单元格文本中提取以 ※ 开头的注释（如限定干员解禁时间等），原样保留。
    """
    if cell is None:
        return []
    text = _cell_text(cell)
    if "※" not in text:
        return []
    # 匹配 ※ 到下一个 ※ 或结尾的片段，去空白
    return [s.strip() for s in re.findall(r"※[^※]+", text) if s.strip()]


def _parse_time_range(s: str) -> tuple[datetime | None, datetime | None]:
    """解析「YYYY-MM-DD HH:MM~YYYY-MM-DD HH:MM」，返回 (start, end)。"""
    s = s.replace("\n", " ").replace("\r", " ")
    m = TIME_RANGE_PATTERN.search(s)
    if not m:
        return None, None
    try:
        start = datetime.strptime(m.group(1).strip(), "%Y-%m-%d %H:%M")
        end = datetime.strptime(m.group(2).strip(), "%Y-%m-%d %H:%M")
        return start, end
    except ValueError:
        return None, None


def _parse_single_time(s: str) -> tuple[datetime | None, datetime | None]:
    """解析单时刻「YYYY-MM-DD HH:MM」，返回 (start, end) 且 end=start+1h。"""
    s = s.replace("\n", " ").replace("\r", " ")
    m = TIME_SINGLE_PATTERN.search(s)
    if not m:
        return None, None
    try:
        start = datetime.strptime(m.group(1).strip(), "%Y-%m-%d %H:%M")
        end = start + timedelta(hours=1)
        return start, end
    except ValueError:
        return None, None


def _title_and_url_from_cell(page_cell) -> tuple[str, str]:
    """从单元格中取标题与 wiki 路径（/w/ 链接，无则标题用单元格文本）。"""
    title, wiki_path = "", ""
    for a in page_cell.find_all("a", href=True):
        href = a.get("href", "")
        if not href.startswith("/w/"):
            continue
        t = _cell_text(a).strip() or a.get("title", "").strip()
        if not t and href:
            t = unquote(href.rstrip("/").split("/")[-1], encoding="utf-8")
        if len(t) > len(title):
            title, wiki_path = t, href
    if not title:
        title = _cell_text(page_cell)
    if not title and wiki_path:
        title = unquote(wiki_path.rstrip("/").split("/")[-1], encoding="utf-8")
    wiki_url = ("https://prts.wiki" + wiki_path) if wiki_path else ""
    return title.strip(), wiki_url


def parse_events_from_html(html: str, source: dict | None = None) -> list[dict]:
    """
    从页面 HTML 解析表格为事件列表。
    source 可选：若含 parse_mode="activity" 则按活动一览表解析（活动开始时间+活动页面）；
    否则按卡池表解析（开启时间+寻访页面）。
    """
    parse_mode = (source or {}).get("parse_mode", "pool")
    if parse_mode == "activity":
        return _parse_activity_table(html)
    return _parse_pool_table(html)


def _parse_activity_table(html: str) -> list[dict]:
    """解析活动一览表：活动开始时间、活动页面、活动分类。"""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_=re.compile(r"wikitable"))
    events = []
    seen: set[tuple[str, str]] = set()

    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"])
        header_text = _cell_text(rows[0])
        if "活动开始时间" not in header_text or "活动页面" not in header_text:
            continue

        col_time = col_page = col_desc = None
        for i, cell in enumerate(header_cells):
            t = _cell_text(cell)
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
            title, wiki_url = _title_and_url_from_cell(cells[col_page])
            if not title:
                continue
            time_str = _cell_text(cells[col_time])
            start, end = _parse_single_time(time_str)
            if start is None:
                continue
            desc = ""
            if col_desc is not None and len(cells) > col_desc:
                desc = _cell_text(cells[col_desc]).strip()
            key = (title, start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            events.append({
                "title": title,
                "start": start,
                "end": end,
                "description": desc,
                "wiki_url": wiki_url,
            })
    return events


def _parse_pool_table(html: str) -> list[dict]:
    """解析卡池表：寻访页面、开启时间、6★/5★ 等。"""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_=re.compile(r"wikitable"))
    events = []
    seen: set[tuple[str, str]] = set()

    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"])
        header_text = _cell_text(rows[0])
        if "开启时间" not in header_text or "寻访页面" not in header_text:
            continue

        col_page = col_time = None
        for i, cell in enumerate(header_cells):
            t = _cell_text(cell)
            if "寻访页面" in t:
                col_page = i
            if "开启时间" in t:
                col_time = i
        if col_page is None or col_time is None:
            continue

        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(col_page, col_time):
                continue
            page_cell, time_cell = cells[col_page], cells[col_time]
            title, wiki_url = _title_and_url_from_cell(page_cell)
            if not title:
                continue
            start, end = _parse_time_range(_cell_text(time_cell))
            if start is None or end is None:
                continue
            desc_parts = []
            if len(cells) > 2:
                six_star = _operator_names_from_cell(cells[2])
                six_notes = _comment_notes_from_cell(cells[2])
                part = "6★: " + "、".join(six_star) if six_star else ""
                if six_notes:
                    part = (part + " " + " ".join(six_notes)) if part else " ".join(six_notes)
                if part:
                    desc_parts.append(part)
            if len(cells) > 3:
                five_four = _operator_names_from_cell(cells[3])
                five_notes = _comment_notes_from_cell(cells[3])
                part = "5★&4★: " + "、".join(five_four) if five_four else ""
                if five_notes:
                    part = (part + " " + " ".join(five_notes)) if part else " ".join(five_notes)
                if part:
                    desc_parts.append(part)
            description = " | ".join(desc_parts).strip()

            key = (title, start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            events.append({
                "title": title,
                "start": start,
                "end": end,
                "description": description,
                "wiki_url": wiki_url,
            })
    return events


def _stable_uid(ev: dict) -> str:
    """同一卡池在不同年份文件中使用相同 UID，便于日历去重。"""
    raw = f"{ev['title']}|{ev['start'].isoformat()}"
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"prts-{ev['start'].strftime('%Y%m%d')}-{h}@prts.wiki"


def build_ics(events: list[dict], calendar_name: str = "明日方舟 限时寻访") -> bytes:
    """使用 icalendar 库根据事件列表生成 ICS 日历内容（返回 UTF-8 字节）。"""
    cal = Calendar()
    cal.add("prodid", "-//PRTS Calendar//prts_calendar//ZH")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", calendar_name)

    now_utc = datetime.utcnow()
    for ev in events:
        event = Event()
        event.add("uid", _stable_uid(ev))
        event.add("dtstamp", now_utc)
        event.add("dtstart", ev["start"])
        event.add("dtend", ev["end"])
        event.add("summary", ev["title"])
        if ev.get("description"):
            event.add("description", ev["description"])
        if ev.get("wiki_url"):
            event.add("url", ev["wiki_url"])
        cal.add_component(event)

    return cal.to_ical()


def events_by_year(events: list[dict]) -> dict[int, list[dict]]:
    """
    按年份分组：卡池覆盖的每一年都计入。
    例如 2025-12-25~2026-01-08 的卡池会同时出现在 2025 与 2026 的列表中。
    每个年份列表中的事件保留完整信息（不截断）。
    """
    by_year: dict[int, list[dict]] = {}
    for ev in events:
        start_y = ev["start"].year
        end_y = ev["end"].year
        for y in range(start_y, end_y + 1):
            by_year.setdefault(y, []).append(ev)
    return by_year


def generate_ics_by_year(
    html: str | None = None,
    events: list | None = None,
    source: dict | None = None,
    output_dir: str = ".",
    output_prefix: str = "prts_calendar",
    calendar_name_base: str = "明日方舟 卡池",
) -> dict[int, int]:
    """
    按年份输出 ICS：每年一个文件，跨年事件同时写入起止年份。
    传入 html 则按 source 解析；传入 events 则直接使用。
    返回 { 年份: 该文件内事件数 }。
    """
    if events is None:
        if html is None:
            raise ValueError("需提供 html 或 events")
        events = parse_events_from_html(html, source=source)
    by_year = events_by_year(events)
    written = {}
    current_year = datetime.now().year
    for year in sorted(by_year.keys()):
        year_events = by_year[year]
        name = f"{calendar_name_base} {year}"
        ics_bytes = build_ics(year_events, calendar_name=name)
        path = os.path.join(output_dir, f"{output_prefix}_{year}.ics")
        with open(path, "wb") as f:
            f.write(ics_bytes)
        written[year] = len(year_events)
        # 当年数据额外写一份 latest，便于订阅「仅今年」
        if year == current_year:
            path_latest = os.path.join(output_dir, f"{output_prefix}_latest.ics")
            with open(path_latest, "wb") as f:
                f.write(ics_bytes)
    return written


if __name__ == "__main__":
    import sys

    from sources import POOL_SOURCES, PRTS_API_URL

    output_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    os.makedirs(output_dir, exist_ok=True)

    try:
        for source in POOL_SOURCES:
            sid = source["id"]
            name = source["name"]
            page_title = source["page_title"]
            api_url = source.get("api_url", PRTS_API_URL)
            mobileformat = source.get("mobileformat", False)
            append_year = source.get("append_year", False)
            years = source.get("years", [])

            if append_year and years:
                print(f"正在通过 API 获取 [{name}]（按年份请求）…")
                all_events = []
                for year in years:
                    title_with_year = f"{page_title}/{year}"
                    try:
                        html = fetch_page_via_api(api_url, title_with_year, mobileformat=mobileformat)
                        all_events.extend(parse_events_from_html(html, source=source))
                    except ValueError as e:
                        print(f"  → {title_with_year} 获取失败: {e}")
                # 按 (title, start) 去重
                seen = set()
                events = []
                for ev in all_events:
                    key = (ev["title"], ev["start"].isoformat())
                    if key not in seen:
                        seen.add(key)
                        events.append(ev)
                by_year = events_by_year(events)
                if not by_year:
                    skip_msg = "未解析到目标表格（开启时间+寻访页面），跳过输出。"
                    print(f"  → {skip_msg}")
                    continue
                counts = generate_ics_by_year(
                    events=events,
                    output_dir=output_dir,
                    output_prefix=sid,
                    calendar_name_base=name,
                )
            else:
                print(f"正在通过 API 获取 [{name}] …")
                html = fetch_page_via_api(api_url, page_title, mobileformat=mobileformat)
                events = parse_events_from_html(html, source=source)
                by_year = events_by_year(events)
                if not by_year:
                    skip_msg = "未解析到目标表格"
                    if source.get("parse_mode") == "activity":
                        skip_msg += "（活动开始时间+活动页面）"
                    else:
                        skip_msg += "（开启时间+寻访页面）"
                    print(f"  → {skip_msg}，跳过输出。")
                    continue
                counts = generate_ics_by_year(
                    html=html,
                    source=source,
                    output_dir=output_dir,
                    output_prefix=sid,
                    calendar_name_base=name,
                )
            total = sum(counts.values())
            print(f"  → 已写入 {len(counts)} 个文件，共 {total} 条事件（跨年已重复计入）。")
            for year in sorted(counts.keys()):
                print(f"     {sid}_{year}.ics  — {counts[year]} 条")
        print("全部完成。")
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
