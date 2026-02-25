# PRTS 日历

从 [PRTS 维基](https://prts.wiki) 拉取**卡池**与**活动**数据，生成 ICS 日历文件，可导入或订阅到系统日历 / 日历应用。

## 订阅链接（Release）

若本仓库已通过 GitHub Actions 发布到 Release（tag: `latest`），可直接用下列**订阅链接**添加到日历应用（如 iOS 日历、Google 日历、Outlook 等），应用会定期拉取更新。

将 `OWNER`、`REPO` 替换为你 fork 后的 GitHub 用户名与仓库名，或本仓库的实际地址：

| 日历 | 订阅链接（仅当年，推荐） |
|------|--------------------------|
| 限时寻访 | `https://github.com/OWNER/REPO/releases/download/latest/prts_limited_recruit_latest.ics` |
| 常驻标准寻访 | `https://github.com/OWNER/REPO/releases/download/latest/prts_standard_latest.ics` |
| 常驻中坚寻访与甄选 | `https://github.com/OWNER/REPO/releases/download/latest/prts_mid_recruit_latest.ics` |
| 活动一览 | `https://github.com/OWNER/REPO/releases/download/latest/prts_activity_latest.ics` |

- 使用 **`*_latest.ics`** 的链接即可长期订阅，每年内容会自动变为当年数据，无需改链接。
- 需要某年完整历史时，可在 [Releases](https://github.com/OWNER/REPO/releases) 页面下载对应 `prts_*_YYYY.ics` 文件后本地导入。

## 本地运行

```bash
pip install -r requirements.txt
python prts_calendar.py          # 输出到 output/
python prts_calendar.py ./my_dir # 输出到指定目录
```

## 自动更新

仓库内 GitHub Actions 会按计划运行，将生成的 ICS 提交到仓库并上传到 Release（tag: `latest`），订阅上述链接即可自动获得更新。

## 数据来源

- 卡池：PRTS 维基「卡池一览」相关页面（限时寻访、常驻标准寻访、常驻中坚寻访&中坚甄选）
- 活动：PRTS 维基「活动一览」

数据通过维基的 MediaWiki API 获取，未做网页爬取。
