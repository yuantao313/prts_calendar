# PRTS 日历

从 [PRTS 维基](https://prts.wiki) 拉取**卡池**与**活动**数据，生成 ICS 日历文件，可导入或订阅到系统日历 / 日历应用。

## 订阅链接（Release）

Actions 会生成两个 Release：

- **当年 + 全量**（tag: `latest`）：`*_latest.ics`（当年订阅用）、`*_all.ics`（全量），适合日常订阅。
- **每年归档**（tag: `archive`）：`prts_*_2019.ics` … `prts_*_2026.ics`，按年下载。

用下列链接在日历应用中**订阅**（推荐用 `*_latest.ics`）：

| 日历 | 订阅链接（当年） |
|------|------------------|
| 限时寻访 | [https://github.com/yuantao313/prts_calendar/releases/download/latest/prts_limited_recruit_latest.ics](https://github.com/yuantao313/prts_calendar/releases/download/latest/prts_limited_recruit_latest.ics) |
| 常驻标准寻访 | [https://github.com/yuantao313/prts_calendar/releases/download/latest/prts_standard_latest.ics](https://github.com/yuantao313/prts_calendar/releases/download/latest/prts_standard_latest.ics) |
| 常驻中坚寻访与甄选 | [https://github.com/yuantao313/prts_calendar/releases/download/latest/prts_mid_recruit_latest.ics](https://github.com/yuantao313/prts_calendar/releases/download/latest/prts_mid_recruit_latest.ics) |
| 活动一览 | [https://github.com/yuantao313/prts_calendar/releases/download/latest/prts_activity_latest.ics](https://github.com/yuantao313/prts_calendar/releases/download/latest/prts_activity_latest.ics) |

- 需要某年或全量时，在 [Releases](https://github.com/yuantao313/prts_calendar/releases) 的 **每年归档** 或 **当年+全量** 中下载对应文件。

## 本地运行

```bash
pip install -r requirements.txt
python prts_calendar.py                    # 默认 --mode all，输出到 output/
python prts_calendar.py --mode yearly      # 仅每年归档
python prts_calendar.py --mode current     # 仅当年 + _latest
python prts_calendar.py --mode full        # 仅全量 *_all.ics
python prts_calendar.py ./my_dir --mode all
```

**构建模式**：`yearly` = 每年归档，`current` = 仅当年+latest，`full` = 仅全量，`all` = 三者都生成（默认）。

## 自动更新

GitHub Actions 定时运行，将 ICS 提交到仓库并上传到上述两个 Release，订阅链接会自动更新。

## 数据来源

- 卡池：PRTS 维基「卡池一览」相关页面（限时寻访、常驻标准寻访、常驻中坚寻访&中坚甄选）
- 活动：PRTS 维基「活动一览」

数据通过维基的 MediaWiki API 获取，未做网页爬取。
