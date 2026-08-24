# PRTS 日历

从 [PRTS 维基](https://prts.wiki) 拉取**卡池**与**活动**数据，生成 ICS 日历文件，可导入或订阅到系统日历 / 日历应用。

## 订阅链接（Jenkins 产物）

Jenkins 定时运行，ICS 作为**构建产物**归档，不再上传 GitHub Release。产物按两个目录组织：

- `output_latest/`：`*_latest.ics`（当年订阅用）、`*_all.ics`（全量），适合日常订阅。
- `output_archive/`：`prts_*_2019.ics` … `prts_*_2026.ics`，按年下载。

产物下载地址为 `<JENKINS_URL>/job/<JOB>/lastSuccessfulBuild/artifact/<路径>`（替换为你的 Jenkins 地址与任务名）：

| 日历 | 产物路径 |
|------|----------|
| 限时寻访 | `output_latest/prts_limited_recruit_latest.ics` |
| 常驻标准寻访 | `output_latest/prts_standard_latest.ics` |
| 常驻中坚寻访与甄选 | `output_latest/prts_mid_recruit_latest.ics` |
| 活动一览 | `output_latest/prts_activity_latest.ics` |

例如：`https://jenkins.example.com/job/prts-calendar/lastSuccessfulBuild/artifact/output_latest/prts_limited_recruit_latest.ics`

- 需要某年或全量时，在 Jenkins 任务页的 **Latest Build → Artifacts** 中下载对应文件。

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

Jenkins 定时运行（每小时第 30 分钟），将 ICS 归档为构建产物，订阅链接会自动更新。

## 数据来源

- 卡池：PRTS 维基「卡池一览」相关页面（限时寻访、常驻标准寻访、常驻中坚寻访&中坚甄选）
- 活动：PRTS 维基「活动一览」

数据通过维基的 MediaWiki API 获取，未做网页爬取。
