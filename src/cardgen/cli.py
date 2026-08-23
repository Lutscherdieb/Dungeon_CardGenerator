"""The `cardgen` command: serve the gallery, move cards in and out, render.

Batch rendering from files still lives in ``generate_card.py`` at the repo root;
this drives the *store*. The two share one renderer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_serve(args) -> int:
    from .web.app import DEFAULT_PORT, serve

    serve(port=args.port or DEFAULT_PORT)
    return 0


def _cmd_import(args) -> int:
    from .store import SessionLocal, import_json_files, init_db

    source = Path(args.path)
    paths = sorted(source.glob("*.json")) if source.is_dir() else [source]
    if not paths:
        print("no .json files under {}".format(source))
        return 1

    init_db()
    with SessionLocal() as db:
        imported, skipped, errors = import_json_files(
            db, paths, replace_existing=args.replace
        )
        db.commit()

    print("imported {}, skipped {}, errors {}".format(len(imported), len(skipped), len(errors)))
    for line in skipped[:10]:
        print("  skipped: {}".format(line))
    if len(skipped) > 10:
        print("  ... and {} more".format(len(skipped) - 10))
    for line in errors:
        print("  ERROR: {}".format(line))
    return 1 if errors else 0


def _cmd_export(args) -> int:
    from .store import SessionLocal, export_json_files, init_db

    init_db()
    with SessionLocal() as db:
        written = export_json_files(db, Path(args.path))
    print("exported {} card(s) to {}".format(len(written), args.path))
    return 0


def _cmd_render(args) -> int:
    from .render import render_and_record
    from .store import SessionLocal, get_card, init_db, list_cards

    init_db()
    failures = 0
    with SessionLocal() as db:
        if args.id:
            rows = [r for r in (get_card(db, i) for i in args.id) if r is not None]
        else:
            rows = list_cards(db)
        if not rows:
            print("nothing to render -- is the store empty? try `cardgen import`")
            return 1
        for index, row in enumerate(rows, 1):
            png = render_and_record(db, row.id)
            state = png or "FAILED: {}".format(row.render_error)
            print("[{}/{}] {:<28} {}".format(index, len(rows), row.name, state))
            if png is None:
                failures += 1
    print("\n{} rendered, {} failed".format(len(rows) - failures, failures))
    return 1 if failures else 0


def _cmd_schemas(args) -> int:
    from .model.schemas import write_schemas

    for path in write_schemas(Path(args.path)):
        print("wrote {}".format(path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cardgen", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the local gallery")
    p.add_argument("--port", type=int, default=None)
    p.set_defaults(func=_cmd_serve)

    p = sub.add_parser("import", help="load card JSON into the store")
    p.add_argument("path", nargs="?", default="data/Mixed")
    p.add_argument("--replace", action="store_true",
                   help="overwrite a stored card when the name already exists")
    p.set_defaults(func=_cmd_import)

    p = sub.add_parser("export", help="write the store back out as card JSON")
    p.add_argument("path", nargs="?", default="data/Mixed")
    p.set_defaults(func=_cmd_export)

    p = sub.add_parser("render", help="render stored cards to print-ready PNGs")
    p.add_argument("--id", type=int, nargs="*", help="render only these card ids")
    p.set_defaults(func=_cmd_render)

    p = sub.add_parser("schemas", help="regenerate schemas/ from the model")
    p.add_argument("path", nargs="?", default="schemas")
    p.set_defaults(func=_cmd_schemas)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
