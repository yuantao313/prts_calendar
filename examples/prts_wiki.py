"""Example: PRTS Wiki 数据源（薄封装，实际逻辑在 calpipe.builtin.prts）。
用法：在 config.json 中既可通过 "type": "prts_wiki" 使用内置版本，
      也可通过 "script": "examples/prts_wiki.py" 以脚本模式加载。
"""
from calpipe.builtin.prts import PrtsWikiSource, _parse_pool_table, _parse_activity_table, _parse_time_range

__all__ = ["PrtsWikiSource", "_parse_pool_table", "_parse_activity_table", "_parse_time_range"]
