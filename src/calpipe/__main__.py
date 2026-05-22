"""calpipe CLI — 通用日历 ICS 生成框架。

原子模式（一对一）：
  calpipe gen --type prts_wiki --id my_cal --name "限时寻访" --params '{"page_title":"卡池一览/限时寻访"}'
  calpipe gen --script my_source.py --id my_cal --name "发薪日" --params '{"pay_day":15}'

批量模式（配置文件）：
  calpipe run --config config.json
"""
import argparse

from calpipe.runner import run_from_config, run_one


def main():
    parser = argparse.ArgumentParser(description="通用日历 ICS 生成框架")
    sub = parser.add_subparsers(dest="command")

    a = sub.add_parser("gen", help="原子模式：一对一生成")
    a.add_argument("--type", help="内置数据源类型")
    a.add_argument("--script", help="外部数据源脚本路径")
    a.add_argument("--id", required=True, help="输出文件前缀")
    a.add_argument("--name", required=True, help="日历名称")
    a.add_argument("--params", default="{}", help="JSON 参数字符串（默认 {}）")
    a.add_argument("--output", default="output", help="输出目录（默认 output）")
    a.add_argument("--mode", choices=["yearly", "current", "full", "all"], default="all")

    c = sub.add_parser("run", help="批量模式：从配置文件加载")
    c.add_argument("--config", default="config.json", help="配置文件路径")
    c.add_argument("--mode", choices=["yearly", "current", "full", "all"], default="all")
    c.add_argument("--output", default=None, help="输出目录覆盖")

    args = parser.parse_args()

    if args.command == "gen":
        if not args.type and not args.script:
            parser.error("gen 模式必须指定 --type 或 --script")
        run_one(
            type=args.type,
            script=args.script,
            source_id=args.id,
            name=args.name,
            params=args.params,
            output_dir=args.output,
            mode=args.mode,
        )
    elif args.command == "run":
        run_from_config(config_path=args.config, mode=args.mode, output_dir_override=args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
