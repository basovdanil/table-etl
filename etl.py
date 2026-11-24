#!/usr/bin/env python3
"""Три операции над табличными выгрузками: слить, сравнить, разложить.

usage: etl.py merge --inputs a.csv b.csv --key id --out merged.csv [--json]
       etl.py diff --old v1.csv --new v2.csv --key id --out diff.csv [--json]
       etl.py split --input v2.csv --by склад --outdir parts [--json]
Коды: 0 — готово, 2 — аргументы, 3 — нет файла, 4 — ошибка данных.
"""
import argparse
import csv
import json
import os
import re
import sys

BAD_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return (reader.fieldnames or []), list(reader)


def write_csv(path, fields, rows):
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_name(value):
    return (BAD_CHARS.sub("_", (value or "").strip()) or "без_значения")[:60]


def merge(args):
    fields, order, seen, rows_in, dups = [], [], {}, 0, 0
    for path in args.inputs:
        if not os.path.exists(path):
            print(f"нет файла: {path}", file=sys.stderr)
            return 3
        head, rows = read_csv(path)
        for name in head:
            if name not in fields:
                fields.append(name)
        if args.key not in head:
            print(f"нет колонки {args.key} в {path}", file=sys.stderr)
            return 4
        for row in rows:
            rows_in += 1
            key = row.get(args.key, "")
            if not key:
                print(f"пустой ключ {args.key} в {path}", file=sys.stderr)
                return 4
            if key in seen:
                dups += 1
                order[seen[key]] = row
                continue
            seen[key] = len(order)
            order.append(row)
    write_csv(args.out, fields, order)
    return {"out": args.out, "files": len(args.inputs), "rows_in": rows_in,
            "rows_out": len(order), "duplicates": dups}


def diff(args):
    for path in (args.old, args.new):
        if not os.path.exists(path):
            print(f"нет файла: {path}", file=sys.stderr)
            return 3
    fields, old = read_csv(args.old)
    new_fields, new = read_csv(args.new)
    fields += [name for name in new_fields if name not in fields]
    if args.key not in fields:
        print(f"нет колонки {args.key}", file=sys.stderr)
        return 4

    old_map = {row[args.key]: row for row in old}
    new_map = {row[args.key]: row for row in new}
    added = [row for key, row in new_map.items() if key not in old_map]
    removed = [row for key, row in old_map.items() if key not in new_map]
    changed, columns = [], []
    for key, row in new_map.items():
        if key not in old_map:
            continue
        cols = [name for name in fields
                if name != args.key and (old_map[key].get(name) or "") != (row.get(name) or "")]
        if cols:
            changed.append(row)
            columns.append({"key": key, "columns": cols})

    out = []
    out += [{**row, "_change": "добавлено", "_columns": ""} for row in added]
    out += [{**row, "_change": "удалено", "_columns": ""} for row in removed]
    for row, meta in zip(changed, columns):
        out.append({**row, "_change": "изменено", "_columns": ",".join(meta["columns"])})
    write_csv(args.out, fields + ["_change", "_columns"], out)
    return {"out": args.out, "rows_old": len(old), "rows_new": len(new),
            "added": len(added), "removed": len(removed), "changed": len(changed),
            "changed_columns": columns}


def split(args):
    if not os.path.exists(args.input):
        print(f"нет файла: {args.input}", file=sys.stderr)
        return 3
    fields, rows = read_csv(args.input)
    if args.by not in fields:
        print(f"нет колонки {args.by}", file=sys.stderr)
        return 4
    groups = {}
    for row in rows:
        groups.setdefault(row.get(args.by, ""), []).append(row)
    manifest, used = {}, set()
    for value, items in groups.items():
        name = safe_name(value) + ".csv"
        while name in used:
            name = name[:-4] + "_.csv"
        used.add(name)
        write_csv(os.path.join(args.outdir, name), fields, items)
        manifest[value] = {"file": name, "rows": len(items)}
    manifest_path = os.path.join(args.outdir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return {"outdir": args.outdir, "parts": len(manifest), "rows": len(rows),
            "manifest": manifest_path, "detail": manifest}


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    merge_p = sub.add_parser("merge", help="слить файлы по ключу, дубли отбросить")
    merge_p.add_argument("--inputs", nargs="+", required=True)
    merge_p.add_argument("--key", required=True)
    merge_p.add_argument("--out", required=True)
    merge_p.add_argument("--json", action="store_true")
    merge_p.set_defaults(func=merge)

    diff_p = sub.add_parser("diff", help="сравнить две версии таблицы")
    diff_p.add_argument("--old", required=True)
    diff_p.add_argument("--new", required=True)
    diff_p.add_argument("--key", required=True)
    diff_p.add_argument("--out", required=True)
    diff_p.add_argument("--json", action="store_true")
    diff_p.set_defaults(func=diff)

    split_p = sub.add_parser("split", help="разложить таблицу по значению колонки")
    split_p.add_argument("--input", required=True)
    split_p.add_argument("--by", required=True)
    split_p.add_argument("--outdir", required=True)
    split_p.add_argument("--json", action="store_true")
    split_p.set_defaults(func=split)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    result = args.func(args)
    if isinstance(result, int):
        return result
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(" ".join(f"{k}={v}" for k, v in result.items() if k != "detail"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
