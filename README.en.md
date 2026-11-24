# table-etl

[![tests](https://github.com/basovdanil/table-etl/actions/workflows/tests.yml/badge.svg)](https://github.com/basovdanil/table-etl/actions/workflows/tests.yml)

Three operations that come up before loading a spreadsheet export into a database: merge several
files, compare two versions, and split a table by a column value. Deduplication keeps the last row
per key.

Standard library only. Input is a CSV as Excel and 1C export it: `;` or `,` separator, UTF-8 or
windows-1251 with BOM.

## Quick start

```
python etl.py merge --inputs reg-01.csv reg-02.csv --key id --out old.csv
python etl.py diff  --old old.csv --new new.csv --key id --out diff.csv
python etl.py split --input new.csv --by warehouse --outdir parts
```

Every command takes `--json` and prints one object to stdout, no colour, no progress — safe to pipe.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | done |
| `2` | bad arguments |
| `3` | file not found |
| `4` | data error: key column missing or empty key |

## Demo

Three synthetic exports: 51 rows with duplicates collapse to 45, 72 collapse to 60; the diff finds
15 added, 1 removed and 1 changed row; the split writes three parts plus `manifest.json`.

## Tests

```
python -m unittest discover -s tests
```

11 tests: column union, duplicate replacement, empty key, missing column, all three diff kinds,
changed-field list, split with manifest, exit codes, `--json` shape.

## Scope

It does not read real 1C files with multi-row headers or merged cells — the format is a flat CSV.
Case write-up: <https://basovdanil.github.io/portfolio/case-tables/case-tables.html>

---

More projects: [github.com/basovdanil](https://github.com/basovdanil) · write-ups: [portfolio](https://basovdanil.github.io/portfolio/)
