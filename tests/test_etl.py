import csv
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import etl


def write(path, fields, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_merge_unions_columns_and_keeps_last_duplicate(self):
        a = os.path.join(self.dir, "a.csv")
        b = os.path.join(self.dir, "b.csv")
        out = os.path.join(self.dir, "out.csv")
        write(a, ["id", "сумма"], [{"id": "1", "сумма": "10"}, {"id": "2", "сумма": "20"}])
        write(b, ["id", "сумма", "статус"],
              [{"id": "2", "сумма": "25", "статус": "оплачен"},
               {"id": "3", "сумма": "30", "статус": "черновик"}])
        code = etl.main(["merge", "--inputs", a, b, "--key", "id", "--out", out])
        self.assertEqual(code, 0)
        rows = read(out)
        self.assertEqual([r["id"] for r in rows], ["1", "2", "3"])
        self.assertEqual(rows[1]["сумма"], "25")
        self.assertEqual(rows[1]["статус"], "оплачен")
        self.assertIn("статус", rows[0])

    def test_merge_missing_file_returns_3(self):
        code = etl.main(["merge", "--inputs", os.path.join(self.dir, "нет.csv"),
                         "--key", "id", "--out", os.path.join(self.dir, "out.csv")])
        self.assertEqual(code, 3)

    def test_merge_without_key_column_returns_4(self):
        a = os.path.join(self.dir, "a.csv")
        write(a, ["номер"], [{"номер": "1"}])
        code = etl.main(["merge", "--inputs", a, "--key", "id",
                         "--out", os.path.join(self.dir, "out.csv")])
        self.assertEqual(code, 4)

    def test_merge_empty_key_returns_4(self):
        a = os.path.join(self.dir, "a.csv")
        write(a, ["id", "сумма"], [{"id": "", "сумма": "10"}])
        code = etl.main(["merge", "--inputs", a, "--key", "id",
                         "--out", os.path.join(self.dir, "out.csv")])
        self.assertEqual(code, 4)


class DiffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.old = os.path.join(self.dir, "old.csv")
        self.new = os.path.join(self.dir, "new.csv")
        self.out = os.path.join(self.dir, "diff.csv")
        write(self.old, ["id", "сумма", "статус"],
              [{"id": "1", "сумма": "10", "статус": "черновик"},
               {"id": "2", "сумма": "20", "статус": "оплачен"},
               {"id": "3", "сумма": "30", "статус": "черновик"}])
        write(self.new, ["id", "сумма", "статус"],
              [{"id": "1", "сумма": "10", "статус": "оплачен"},
               {"id": "3", "сумма": "30", "статус": "черновик"},
               {"id": "4", "сумма": "40", "статус": "черновик"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_diff_reports_added_removed_changed(self):
        code = etl.main(["diff", "--old", self.old, "--new", self.new,
                         "--key", "id", "--out", self.out])
        self.assertEqual(code, 0)
        rows = read(self.out)
        changes = {r["id"]: r["_change"] for r in rows}
        self.assertEqual(changes, {"1": "изменено", "2": "удалено", "4": "добавлено"})
        changed = [r for r in rows if r["id"] == "1"][0]
        self.assertEqual(changed["_columns"], "статус")

    def test_diff_json_reports_changed_columns(self):
        result = etl.diff(type("A", (), {
            "old": self.old, "new": self.new, "key": "id", "out": self.out,
            "json": True})())
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["changed"], 1)
        self.assertEqual(result["changed_columns"], [{"key": "1", "columns": ["статус"]}])

    def test_diff_missing_file_returns_3(self):
        code = etl.main(["diff", "--old", os.path.join(self.dir, "нет.csv"),
                         "--new", self.new, "--key", "id", "--out", self.out])
        self.assertEqual(code, 3)

    def test_diff_without_key_column_returns_4(self):
        code = etl.main(["diff", "--old", self.old, "--new", self.new,
                         "--key", "номер", "--out", self.out])
        self.assertEqual(code, 4)


class SplitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.src = os.path.join(self.dir, "rows.csv")
        write(self.src, ["id", "склад"],
              [{"id": "1", "склад": "Москва"}, {"id": "2", "склад": "Казань"},
               {"id": "3", "склад": "Москва"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_writes_parts_and_manifest(self):
        outdir = os.path.join(self.dir, "parts")
        code = etl.main(["split", "--input", self.src, "--by", "склад", "--outdir", outdir])
        self.assertEqual(code, 0)
        with open(os.path.join(outdir, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["Москва"], {"file": "Москва.csv", "rows": 2})
        self.assertEqual(len(read(os.path.join(outdir, "Казань.csv"))), 1)

    def test_split_without_column_returns_4(self):
        code = etl.main(["split", "--input", self.src, "--by", "город",
                         "--outdir", os.path.join(self.dir, "parts")])
        self.assertEqual(code, 4)


class CliTest(unittest.TestCase):
    def test_json_output_is_parsable(self):
        import io
        from contextlib import redirect_stdout
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "a.csv")
        write(path, ["id"], [{"id": "1"}])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = etl.main(["merge", "--inputs", path, "--key", "id",
                             "--out", os.path.join(tmp.name, "out.csv"), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["rows_out"], 1)


if __name__ == "__main__":
    unittest.main()
