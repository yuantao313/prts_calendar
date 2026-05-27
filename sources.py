"""
PRTS 日历数据源配置（API 数据源）。
每项：id、name、page_title。可选 append_year、parse_mode（pool/activity）等。
"""

PRTS_API_URL = "https://prts.wiki/api.php"
PRTS_MOBILE_API_URL = "https://m.prts.wiki/api.php"
DEFAULT_YEAR_RANGE = list(range(2019, 2027))  # 2019～2026

# 所有数据源（卡池 + 活动）
POOL_SOURCES = [
    {
        "id": "prts_limited_recruit",
        "name": "明日方舟 限时寻访",
        "page_title": "卡池一览/限时寻访",
    },
    {
        "id": "prts_standard",
        "name": "明日方舟 常驻标准寻访",
        "page_title": "卡池一览/常驻标准寻访",
        "append_year": True,
        "years": DEFAULT_YEAR_RANGE,
        "api_url": "https://m.prts.wiki/api.php",
        "mobileformat": True,
    },
    {
        "id": "prts_mid_recruit",
        "name": "明日方舟 常驻中坚寻访与甄选",
        "page_title": "卡池一览/常驻中坚寻访&中坚甄选",
        "append_year": True,
        "years": list(range(2023, 2027)),
        "api_url": "https://m.prts.wiki/api.php",
        "mobileformat": True,
    },
    {
        "id": "prts_activity",
        "name": "明日方舟 活动一览",
        "page_title": "活动一览",
        "api_url": "https://m.prts.wiki/api.php",
        "mobileformat": True,
        "parse_mode": "activity",
    },
]
