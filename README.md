# calpipe — 通用日历 ICS 生成框架

将任意数据源转化为可订阅的 ICS 日历。内置 PRTS Wiki（明日方舟）、中国法定节假日、发薪日、华为月末周六等数据源，也可用任何 `.py` 脚本扩展。

## 特性

- **任意数据源** — 继承 `DataSource` 基类写一个 `.py`，填进配置即可生成 ICS
- **内置 + 脚本** — 常用源内置调用，自定义源走动态脚本加载
- **原子化 CLI** — 每次调用只生成一个数据源，适合 CI/CD 编排
- **GitHub Actions 双流水线** — PRTS 每小时更新，发薪日/节假日每月更新
- **订阅友好** — 输出 `_latest.ics`（当年）和 `_all.ics`（全量），日历 App 直接订阅

## 安装

```bash
git clone git@github.com:yuantao313/prts_calendar.git
cd prts_calendar
uv sync
```

## 快速开始

### 原子模式（一对一生成）

```bash
# 内置数据源
uv run calpipe gen --type prts_wiki --id prts_limited \
  --name '明日方舟 限时寻访' \
  --params '{"page_title":"卡池一览/限时寻访"}'

# 外部脚本
uv run calpipe gen --script examples/company_payday.py --id payday \
  --name '公司发薪日' \
  --params '{"pay_day":15,"strategy":"advance","years":[2025,2026]}'

# 华为月末周六
uv run calpipe gen --script examples/huawei_last_saturday.py --id huawei \
  --name '华为月末周六加班' \
  --params '{"years":[2025]}'
```

### 批量模式（配置文件）

```bash
uv run calpipe run --config config.json
```

## 内置数据源

| 类型 | 说明 |
|------|------|
| `prts_wiki` | 明日方舟卡池/活动一览（MediaWiki API） |

## 示例数据源（`examples/`）

| 文件 | 用途 |
|------|------|
| `chinese_holidays.py` | 中国法定节假日（timor.tech API） |
| `company_payday.py` | 公司发薪日（提前/延后/不调整） |
| `huawei_last_saturday.py` | 华为月末周六加班（法定假日/调休跳过，7天规则） |
| `prts_wiki.py` | PRTS Wiki（薄封装，实际逻辑在内置中） |

## 写自己的数据源

```python
# my_source.py
from calpipe.base import DataSource
from datetime import datetime

class MySource(DataSource):
    def __init__(self, source_id, name, params):
        super().__init__(source_id, name, params)
        self.count = params.get("count", 1)

    def get_events(self):
        return [
            {"title": f"事件 {i}", "start": datetime(2025, 6, i, 9),
             "end": datetime(2025, 6, i, 10)}
            for i in range(1, self.count + 1)
        ]
```

```
calpipe gen --script my_source.py --id my_cal --name "我的日历" --params '{"count":5}'
```

## CLI 参考

```
calpipe gen                   # 原子模式：一对一生成
  --type TYPE                 内置数据源类型
  --script SCRIPT             外部脚本路径
  --id ID                     输出文件前缀（必需）
  --name NAME                 日历名称（必需）
  --params PARAMS             JSON 参数字符串（默认 {}）
  --output OUTPUT             输出目录
  --mode {yearly,current,full,all}

calpipe run                   # 批量模式：加载配置文件
  --config CONFIG
  --mode {yearly,current,full,all}
  --output OUTPUT
```

## 订阅链接

### PRTS 日历（每小时更新）

| 日历 | `_latest.ics`（订阅用） |
|------|------------------------|
| 限时寻访 | [`prts_limited_recruit_latest.ics`](https://github.com/yuantao313/prts_calendar/releases/download/prts-latest/prts_limited_recruit_latest.ics) |
| 常驻标准寻访 | [`prts_standard_latest.ics`](https://github.com/yuantao313/prts_calendar/releases/download/prts-latest/prts_standard_latest.ics) |
| 中坚寻访 | [`prts_mid_recruit_latest.ics`](https://github.com/yuantao313/prts_calendar/releases/download/prts-latest/prts_mid_recruit_latest.ics) |
| 活动一览 | [`prts_activity_latest.ics`](https://github.com/yuantao313/prts_calendar/releases/download/prts-latest/prts_activity_latest.ics) |

### 发薪日日历（每月更新）

| 日历 | `_latest.ics`（订阅用） |
|------|------------------------|
| 法定节假日 | [`chinese_holidays_latest.ics`](https://github.com/yuantao313/prts_calendar/releases/download/payday/chinese_holidays_latest.ics) |
| 公司发薪日 | [`company_payday_latest.ics`](https://github.com/yuantao313/prts_calendar/releases/download/payday/company_payday_latest.ics) |
| 月末周六加班 | [`huawei_last_saturday_latest.ics`](https://github.com/yuantao313/prts_calendar/releases/download/payday/huawei_last_saturday_latest.ics) |

## 自动更新

两条独立 GitHub Actions 流水线，互不干扰：

| 流水线 | 频率 | Release | 内容 |
|--------|------|---------|------|
| `prts-calendar.yml` | 每小时 | `prts-archive` + `prts-latest` | 明日方舟卡池/活动 |
| `payday-calendar.yml` | 每月 1 日 | `payday` | 节假日 + 发薪日 + 月末加班 |

## 项目结构

```
src/calpipe/          # 核心框架
  base.py             #   DataSource 抽象基类
  loader.py           #   动态脚本加载
  runner.py           #   配置驱动运行器 + 原子模式
  utils.py            #   ICS 构建
  builtin/            #   内置数据源注册表
    prts.py           #     PRTS Wiki
examples/             # 示例数据源
tests/                # 38 项测试
```

## 许可证

MIT
