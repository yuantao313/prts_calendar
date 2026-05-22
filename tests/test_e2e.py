"""E2E tests for the generic calendar framework."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from calpipe.base import DataSource
from calpipe.builtin import BUILTINS
from calpipe.loader import load_source_class
from calpipe.runner import run_from_config, run_one, _resolve_source_class
from calpipe.utils import build_ics, events_by_year


class TestDataSourceBase:
    def test_base_class_interface(self):
        class DummySource(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)

            def get_events(self):
                return [{
                    "title": "test",
                    "start": datetime(2025, 6, 15),
                    "end": datetime(2025, 6, 16),
                    "description": "desc",
                }]

        ds = DummySource("test_id", "Test", {})
        assert ds.source_id == "test_id"
        assert ds.name == "Test"

        events = ds.collect_events()
        assert len(events) == 1
        assert events[0]["url"] == ""


class TestLoader:
    def test_loader_discovers_source_class(self):
        code = textwrap.dedent("""
        from datetime import datetime
        from calpipe.base import DataSource

        class MySource(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)
                self.message = params.get("message", "")

            def get_events(self):
                return [{"title": self.message, "start": datetime(2025,1,1), "end": datetime(2025,1,2)}]
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            script_path = f.name

        try:
            cls = load_source_class(script_path)
            assert issubclass(cls, DataSource)
            instance = cls(source_id="t", name="T", params={"message": "hello"})
            events = instance.collect_events()
            assert len(events) == 1
            assert events[0]["title"] == "hello"
        finally:
            os.unlink(script_path)

    def test_loader_raises_on_no_source(self):
        code = "x = 1"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            script_path = f.name

        try:
            with pytest.raises(ValueError, match="未找到 DataSource 子类"):
                load_source_class(script_path)
        finally:
            os.unlink(script_path)


class TestDynamicScriptIntegration:
    """Simulate a user writing their own source script and loading it via config."""

    def test_custom_source_via_loader(self):
        code = textwrap.dedent("""
        from datetime import datetime
        from calpipe.base import DataSource

        class CustomSource(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)
                self.count = params.get("count", 1)

            def get_events(self):
                return [
                    {"title": f"Event {i}", "start": datetime(2025, 6, i, 9), "end": datetime(2025, 6, i, 10)}
                    for i in range(1, self.count + 1)
                ]
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            script_path = f.name

        try:
            cls = load_source_class(script_path)
            source = cls(source_id="custom", name="Custom", params={"count": 3})
            events = source.collect_events()
            assert len(events) == 3
            assert events[0]["title"] == "Event 1"
            assert events[2]["title"] == "Event 3"
        finally:
            os.unlink(script_path)


class TestICSBuilding:
    def test_build_ics(self):
        events = [{
            "title": "Test Event",
            "start": datetime(2025, 6, 15),
            "end": datetime(2025, 6, 16),
            "description": "Test Description",
            "url": "https://example.com",
        }]
        ics = build_ics(events, "Test Calendar", "test")
        assert b"BEGIN:VCALENDAR" in ics
        assert b"VEVENT" in ics
        assert b"Test Event" in ics

    def test_events_by_year_single(self):
        events = [{"title": "E1", "start": datetime(2025, 1, 1), "end": datetime(2025, 1, 2)}]
        by_year = events_by_year(events)
        assert 2025 in by_year
        assert len(by_year[2025]) == 1

    def test_events_by_year_cross(self):
        events = [{"title": "X", "start": datetime(2025, 12, 25), "end": datetime(2026, 1, 5)}]
        by_year = events_by_year(events)
        assert 2025 in by_year and 2026 in by_year


class TestRunFromConfigE2E:
    def test_run_with_dynamic_source(self):
        source_code = textwrap.dedent("""
        from datetime import datetime
        from calpipe.base import DataSource

        class MyPayday(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)
                self.pay_day = params.get("pay_day", 15)

            def get_events(self):
                from datetime import date, timedelta
                events = []
                for m in range(1, 13):
                    d = date(2025, m, self.pay_day)
                    events.append({
                        "title": f"Pay {m}",
                        "start": datetime(2025, m, d.day),
                        "end": datetime(2025, m, d.day) + timedelta(days=1),
                    })
                return events
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "my_source.py")
            with open(script_path, "w") as f:
                f.write(source_code)

            config = {
                "output_dir": tmpdir,
                "sources": [{
                    "id": "my_pay",
                    "name": "My Payday",
                    "script": script_path,
                    "params": {"pay_day": 10},
                }],
            }
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w") as f:
                json.dump(config, f)

            run_from_config(config_path=config_path, mode="all", output_dir_override=tmpdir)

            ics_files = sorted([x for x in os.listdir(tmpdir) if x.endswith(".ics")])
            assert len(ics_files) >= 1
            assert any("my_pay" in x for x in ics_files)

    def test_run_multiple_sources(self):
        source_code = textwrap.dedent("""
        from datetime import datetime, timedelta
        from calpipe.base import DataSource

        class SimpleSource(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)
            def get_events(self):
                return [{"title": "E", "start": datetime(2025,1,1), "end": datetime(2025,1,2)}]
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "source.py")
            with open(script_path, "w") as f:
                f.write(source_code)

            config = {
                "output_dir": tmpdir,
                "sources": [
                    {"id": "a", "name": "A", "script": script_path, "params": {}},
                    {"id": "b", "name": "B", "script": script_path, "params": {}},
                    {"id": "c", "name": "C", "script": script_path, "params": {}},
                ],
            }
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w") as f:
                json.dump(config, f)

            run_from_config(config_path=config_path, mode="all", output_dir_override=tmpdir)

            ics_files = sorted([x for x in os.listdir(tmpdir) if x.endswith(".ics")])
            for prefix in ["a", "b", "c"]:
                assert any(x.startswith(prefix) for x in ics_files), f"Missing {prefix}"


class TestBuiltins:
    def test_builtins_registry_has_prts(self):
        assert "prts_wiki" in BUILTINS
        from calpipe.builtin.prts import PrtsWikiSource
        assert BUILTINS["prts_wiki"] is PrtsWikiSource

    def test_resolve_by_type(self):
        source_cls = _resolve_source_class({"type": "prts_wiki"})
        from calpipe.builtin.prts import PrtsWikiSource
        assert source_cls is PrtsWikiSource

    def test_resolve_by_script(self):
        code = textwrap.dedent("""
        from datetime import datetime
        from calpipe.base import DataSource
        class XSource(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)
            def get_events(self):
                return [{"title": "x", "start": datetime(2025,1,1), "end": datetime(2025,1,2)}]
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            script_path = f.name
        try:
            source_cls = _resolve_source_class({"script": script_path})
            assert issubclass(source_cls, DataSource)
        finally:
            os.unlink(script_path)

    def test_resolve_unknown_type_raises(self):
        with pytest.raises(ValueError, match="未知的内置数据源类型"):
            _resolve_source_class({"type": "no_such_type"})

    def test_resolve_missing_both_raises(self):
        with pytest.raises(ValueError, match="缺少 'type' 或 'script'"):
            _resolve_source_class({})

    def test_builtin_prts_source_instantiate(self):
        from calpipe.builtin.prts import PrtsWikiSource
        source = PrtsWikiSource(source_id="test", name="Test", params={"page_title": "卡池一览/限时寻访"})
        assert source.source_id == "test"
        assert source.parse_mode == "pool"

    def test_builtin_prts_via_config_e2e(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "output_dir": tmpdir,
                "sources": [{
                    "type": "prts_wiki",
                    "id": "test_prts",
                    "name": "Test PRTS",
                    "params": {"page_title": "卡池一览/限时寻访"},
                }],
            }
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w") as f:
                json.dump(config, f)

            run_from_config(config_path=config_path, mode="all", output_dir_override=tmpdir)

            ics_files = sorted([x for x in os.listdir(tmpdir) if x.endswith(".ics")])
            assert len(ics_files) >= 1
            assert any("test_prts" in x for x in ics_files)

    def test_mixed_builtin_and_script(self):
        code = textwrap.dedent("""
        from datetime import datetime
        from calpipe.base import DataSource
        class CustomSource(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)
            def get_events(self):
                return [{"title": "C", "start": datetime(2025,1,1), "end": datetime(2025,1,2)}]
        """)
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "custom.py")
            with open(script_path, "w") as f:
                f.write(code)
            config = {
                "output_dir": tmpdir,
                "sources": [
                    {"type": "prts_wiki", "id": "builtin_src", "name": "B", "params": {"page_title": "卡池一览/限时寻访"}},
                    {"script": script_path, "id": "script_src", "name": "S", "params": {}},
                ],
            }
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w") as f:
                json.dump(config, f)
            run_from_config(config_path=config_path, mode="all", output_dir_override=tmpdir)
            ics_files = sorted([x for x in os.listdir(tmpdir) if x.endswith(".ics")])
            for prefix in ["builtin_src", "script_src"]:
                assert any(x.startswith(prefix) for x in ics_files), f"Missing {prefix}"


class TestAtomicRunOne:
    """Test run_one() — the atomic CLI mode."""

    def test_atomic_builtin_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_one(
                type="prts_wiki",
                source_id="atomic_test",
                name="Atomic PRTS",
                params='{"page_title":"卡池一览/限时寻访"}',
                output_dir=tmpdir,
                mode="all",
            )
            ics_files = sorted([x for x in os.listdir(tmpdir) if x.endswith(".ics")])
            assert any(x.startswith("atomic_test") for x in ics_files)

    def test_atomic_script(self):
        code = textwrap.dedent("""
        from datetime import datetime
        from calpipe.base import DataSource
        class AtomicSource(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)
            def get_events(self):
                return [{"title": "A", "start": datetime(2025,1,1), "end": datetime(2025,1,2)}]
        """)
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = os.path.join(tmpdir, "atomic_source.py")
            with open(sp, "w") as f:
                f.write(code)
            run_one(
                script=sp,
                source_id="atomic_script",
                name="Atomic Script",
                params="{}",
                output_dir=tmpdir,
                mode="all",
            )
            ics_files = sorted([x for x in os.listdir(tmpdir) if x.endswith(".ics")])
            assert any(x.startswith("atomic_script") for x in ics_files)

    def test_atomic_no_type_or_script_raises(self):
        with pytest.raises(ValueError, match="必须指定"):
            run_one(source_id="x", name="X")

    def test_atomic_bad_json_params(self):
        with tempfile.TemporaryDirectory() as tmpdir, pytest.raises(ValueError, match="JSON 解析失败"):
            run_one(type="prts_wiki", source_id="x", name="X", params="{bad", output_dir=tmpdir)

    def test_multiple_atomic_invocations(self):
        code = textwrap.dedent("""
        from datetime import datetime
        from calpipe.base import DataSource
        class AtomSource(DataSource):
            def __init__(self, source_id, name, params):
                super().__init__(source_id, name, params)
            def get_events(self):
                return [{"title": "X", "start": datetime(2025,1,1), "end": datetime(2025,1,2)}]
        """)
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = os.path.join(tmpdir, "atom.py")
            with open(sp, "w") as f:
                f.write(code)
            run_one(type="prts_wiki", source_id="a", name="A",
                    params='{"page_title":"卡池一览/限时寻访"}', output_dir=tmpdir)
            run_one(script=sp, source_id="b", name="B",
                    params="{}", output_dir=tmpdir)
            run_one(type="prts_wiki", source_id="c", name="C",
                    params='{"page_title":"活动一览","api_url":"https://m.prts.wiki/api.php","mobileformat":true,"parse_mode":"activity"}', output_dir=tmpdir)
            ics_files = sorted([x for x in os.listdir(tmpdir) if x.endswith(".ics")])
            for prefix in ["a", "b", "c"]:
                assert any(x.startswith(prefix) for x in ics_files), f"Missing {prefix}"


class TestRealExamples:
    """Test the actual example source scripts in examples/."""

    def test_chinese_holidays_import(self):
        cls = load_source_class("examples/chinese_holidays.py")
        assert issubclass(cls, DataSource)

    def test_chinese_holidays_get_events(self):
        cls = load_source_class("examples/chinese_holidays.py")
        source = cls(source_id="t", name="T", params={"years": [2025]})
        events = source.collect_events()
        assert len(events) > 0
        for ev in events:
            assert "title" in ev
            assert "start" in ev
            assert ev["end"] > ev["start"]

    def test_company_payday_basic(self):
        cls = load_source_class("examples/company_payday.py")
        source = cls(source_id="t", name="T", params={"pay_day": 15, "strategy": "advance", "years": [2025]})
        events = source.collect_events()
        assert len(events) == 12
        for ev in events:
            assert "发薪日" in ev["title"]
            assert ev["start"].hour == 0

    def test_company_payday_delay_strategy(self):
        cls = load_source_class("examples/company_payday.py")
        source = cls(source_id="t", name="T", params={"pay_day": 15, "strategy": "delay", "years": [2025]})
        events = source.collect_events()
        assert len(events) == 12
        # June 15 2025 is Sunday → should delay to June 16 (Monday)
        jun_event = events[5]
        assert jun_event["start"].day == 16

    def test_company_payday_different_day(self):
        cls = load_source_class("examples/company_payday.py")
        source = cls(source_id="t", name="T", params={"pay_day": 10, "strategy": "none", "years": [2025]})
        events = source.collect_events()
        for ev in events:
            assert ev["start"].day in (10, 28)  # Feb has 28 days

    def test_prts_wiki_import(self):
        cls = load_source_class("examples/prts_wiki.py")
        assert issubclass(cls, DataSource)

    def test_prts_wiki_table_parsing(self):
        from examples.prts_wiki import _parse_pool_table, _parse_activity_table, _parse_time_range

        start, end = _parse_time_range("2025-06-15 12:00~2025-06-20 03:59")
        assert start == datetime(2025, 6, 15, 12, 0)
        assert end == datetime(2025, 6, 20, 3, 59)

        assert _parse_pool_table("<html></html>") == []
        assert _parse_activity_table("<html></html>") == []


class TestHuaweiLastSaturday:
    """Test the Huawei last-Saturday overtime logic."""

    def test_last_saturday_calculation(self):
        from examples.huawei_last_saturday import _last_saturday
        # March 2025: last day is Monday 31, last Saturday is March 29
        assert _last_saturday(2025, 3) == date(2025, 3, 29)
        # Feb 2025: last day is Friday 28, last Saturday is Feb 22
        assert _last_saturday(2025, 2) == date(2025, 2, 22)
        # Jan 2025: last day is Friday 31, last Saturday is Jan 25
        assert _last_saturday(2025, 1) == date(2025, 1, 25)
        assert _last_saturday(2025, 1).weekday() == 5

    def test_should_work_normal_saturday(self):
        from examples.huawei_last_saturday import HuaweiLastSaturday, _last_saturday
        source = HuaweiLastSaturday("t", "T", {"years": [2025]})
        source._cal._holidays = set()
        source._cal._tiaoxiu_cache = {}
        source._cal._fetched = True
        source._cal.is_rest_day = lambda d: d.weekday() >= 5  # only weekends rest
        sat = _last_saturday(2025, 1)
        assert sat == date(2025, 1, 25)
        # backward: 5 weekdays + 1(Sat) = 6. forward: Sun rest. total 6 < 7.
        assert source._should_work(sat) is True

    def test_should_skip_holiday(self):
        from examples.huawei_last_saturday import HuaweiLastSaturday, _last_saturday
        source = HuaweiLastSaturday("t", "T", {"years": [2025]})
        source._cal._holidays = {"2025-01-25"}  # make Jan 25 a holiday
        source._cal._tiaoxiu_cache = {}
        source._cal._fetched = True
        assert source._should_work(date(2025, 1, 25)) is False

    def test_should_skip_tiaoxiu(self):
        from examples.huawei_last_saturday import HuaweiLastSaturday, _last_saturday
        source = HuaweiLastSaturday("t", "T", {"years": [2025]})
        source._cal._holidays = set()
        source._cal._tiaoxiu_cache = {"2025-01-25": True}
        source._cal._fetched = True
        assert source._should_work(date(2025, 1, 25)) is False

    def test_should_skip_7day_rule(self):
        """All days are workdays → any count triggers >= 7 immediately."""
        from examples.huawei_last_saturday import HuaweiLastSaturday
        source = HuaweiLastSaturday("t", "T", {"years": [2025]})
        source._cal._holidays = set()
        source._cal._tiaoxiu_cache = {}
        source._cal._fetched = True
        source._cal.is_rest_day = lambda d: False
        assert source._should_work(date(2025, 2, 1)) is False

    def test_should_skip_bidirectional_7day(self):
        """5 workdays before + 1 after (调休) = 7 consecutive → skip."""
        from examples.huawei_last_saturday import HuaweiLastSaturday
        source = HuaweiLastSaturday("t", "T", {"years": [2025]})
        source._cal._holidays = set()
        source._cal._tiaoxiu_cache = {}
        source._cal._fetched = True

        # Sep 27 Sat: 5 back + 1(Sat) + 1 forward(调休) = 7
        # Simulate: Mon-Fri work, Sat o/t, Sun 调休 work
        source._cal.is_rest_day = lambda d: (
            d < date(2025, 9, 22) or (d > date(2025, 9, 28))
        )
        assert source._should_work(date(2025, 9, 27)) is False

    def test_sep_2025_guoqing_tiaoxiu_skip(self):
        """Real scenario: Sep 27 2025 last Sat + Sep 28 调休 = 9 days streak → skip."""
        from examples.huawei_last_saturday import HuaweiLastSaturday, _last_saturday
        source = HuaweiLastSaturday("t", "T", {"years": [2025]})
        source._cal._holidays = set()
        source._cal._tiaoxiu_cache = {}
        source._cal._fetched = True

        # Sep 2025: Sep 28(日) is 国庆调休 workday, Oct 1-3 国庆 holiday
        source._cal._tiaoxiu_cache = {"2025-09-28": True}
        source._cal._holidays = {"2025-10-01", "2025-10-02", "2025-10-03"}
        source._cal._fetched = True

        # Rest day: holiday OR (weekend AND NOT 调休)
        source._cal.is_rest_day = lambda d: (
            d.strftime("%Y-%m-%d") in {"2025-10-01", "2025-10-02", "2025-10-03"}
            or (d.weekday() >= 5 and d.strftime("%Y-%m-%d") != "2025-09-28")
        )

        sat = _last_saturday(2025, 9)
        assert sat == date(2025, 9, 27)
        assert source._cal.is_holiday(sat) is False
        assert source._cal.is_tiaoxiu(sat) is False
        # Sep 28 调休 → backward: Sep 26-22 (5 workdays). forward: Sep 28-30 (3 workdays).
        # Total: 1 + 5 + 3 = 9 >= 7 → skip
        assert source._should_work(sat) is False

    def test_import_loadable(self):
        cls = load_source_class("examples/huawei_last_saturday.py")
        assert issubclass(cls, DataSource)

    def test_generate_basic_events(self):
        from examples.huawei_last_saturday import HuaweiLastSaturday
        source = HuaweiLastSaturday("t", "T", {"years": [2025]})
        # Mock to make all days work-eligible (no holidays, no 调休, no 7-day)
        source._cal._holidays = set()
        source._cal._tiaoxiu_cache = {}
        source._cal._fetched = True
        source._cal.is_rest_day = lambda d: d.weekday() >= 5  # only weekends rest

        events = source.collect_events()
        # Most months have last Saturday that works (some may have 7-day rule hit)
        assert len(events) >= 6  # at least half the months
        for ev in events:
            assert "月末周六加班" in ev["title"]
            # Event should start at 9am on a Saturday
            assert ev["start"].hour == 9
            assert ev["start"].weekday() == 5
            assert ev["end"].hour == 18

    def test_atomic_cli_invocation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_one(
                script="examples/huawei_last_saturday.py",
                source_id="huawei_test",
                name="华为月末周六测试",
                params='{"years":[2025]}',
                output_dir=tmpdir,
                mode="all",
            )
            ics_files = sorted([x for x in os.listdir(tmpdir) if x.endswith(".ics")])
            assert any(x.startswith("huawei_test") for x in ics_files)
