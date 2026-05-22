"""Generic runner: atomic CLI or batch config.json — resolves built-in / script sources, generates ICS."""
from __future__ import annotations

import json
import os
import sys

from calpipe.builtin import BUILTINS
from calpipe.loader import load_source_class
from calpipe.utils import generate_ics_by_year, generate_ics_full


def _resolve_source_class(source_cfg: dict) -> type:
    if "type" in source_cfg:
        t = source_cfg["type"]
        if t not in BUILTINS:
            raise ValueError(f"未知的内置数据源类型: {t!r}，可用: {list(BUILTINS)}")
        return BUILTINS[t]
    if "script" in source_cfg:
        return load_source_class(source_cfg["script"])
    raise ValueError("数据源配置缺少 'type' 或 'script' 字段")


def _gen(source, output_dir, mode):
    build_yearly = mode in ("yearly", "all")
    build_current = mode in ("current", "all")
    build_full = mode in ("full", "all")
    only_current_year = mode == "current"
    sid, name = source.source_id, source.name

    events = source.collect_events()
    if not events:
        print(f"  → 未获取到事件，跳过。")
        return

    if build_yearly or build_current:
        counts = generate_ics_by_year(
            events=events, source_id=sid, calendar_name=name,
            uid_prefix=source.uid_prefix, output_dir=output_dir,
            only_current_year=only_current_year,
        )
        total = sum(counts.values())
        print(f"  → 已写入 {len(counts)} 个年份文件，共 {total} 条事件。")
        for y in sorted(counts):
            print(f"     {sid}_{y}.ics  — {counts[y]} 条")

    if build_full:
        generate_ics_full(events=events, source_id=sid, calendar_name=name,
                          uid_prefix=source.uid_prefix, output_dir=output_dir)
        print(f"  → 已写入 {sid}_all.ics（全量）")


def run_one(
    *,
    type: str | None = None,
    script: str | None = None,
    source_id: str,
    name: str,
    params: str = "{}",
    output_dir: str = "output",
    mode: str = "all",
) -> None:
    """Atomic: generate ICS for a single data source from CLI flags."""
    cfg: dict = {}
    if type:
        cfg["type"] = type
    elif script:
        cfg["script"] = script
    else:
        raise ValueError("必须指定 --type 或 --script")

    try:
        p = json.loads(params)
    except json.JSONDecodeError as e:
        raise ValueError(f"--params JSON 解析失败: {e}") from e

    label = type or script
    print(f"正在加载 [{name}] <- {label} …")

    cls = _resolve_source_class(cfg)
    source = cls(source_id=source_id, name=name, params=p)
    _gen(source, output_dir, mode)


def run_from_config(
    config_path: str = "config.json",
    mode: str = "all",
    output_dir_override: str | None = None,
) -> None:
    """Batch: read config.json, generate ICS for every source listed."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    output_dir = output_dir_override or config.get("output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)

    try:
        for source_cfg in config.get("sources", []):
            source_id = source_cfg["id"]
            name = source_cfg.get("name", source_id)
            params = source_cfg.get("params", {})
            label = source_cfg.get("type") or source_cfg.get("script")
            print(f"正在加载 [{name}] <- {label} …")

            cls = _resolve_source_class(source_cfg)
            source = cls(source_id=source_id, name=name, params=params)
            _gen(source, output_dir, mode)

        print("全部完成。")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
