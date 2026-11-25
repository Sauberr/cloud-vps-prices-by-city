"""Checks the published data files: columns, types, no gaps, sane prices, and that the summary
agrees with the full table. Runs offline on the files in data/."""

import csv
import json
import os
import unittest

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
PROVIDERS = {"vultr", "digitalocean", "linode", "hetzner"}
COLUMNS = ["provider", "plan", "family", "cpu", "arch", "vcpu", "ram_gb", "disk_gb", "transfer_tb",
           "region", "city", "country", "continent", "price_month_usd", "price_hour_usd",
           "ipv4_extra_month_usd", "price_month_with_ipv4_usd"]


def read(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Prices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read("prices.csv")

    def test_columns(self):
        with open(os.path.join(DATA, "prices.csv"), encoding="utf-8") as f:
            self.assertEqual(f.readline().strip().split(","), COLUMNS)

    def test_every_provider_present(self):
        self.assertEqual({r["provider"] for r in self.rows}, PROVIDERS)

    def test_no_empty_cells(self):
        for r in self.rows:
            for col in COLUMNS:
                self.assertNotEqual(r[col], "", f"{col} empty in {r['provider']} {r['plan']} {r['region']}")

    def test_values(self):
        for r in self.rows:
            self.assertIn(r["cpu"], {"shared", "dedicated"})
            self.assertIn(r["arch"], {"x86", "arm"})
            self.assertEqual(len(r["country"]), 2)
            self.assertGreaterEqual(int(r["vcpu"]), 1)
            month, hour = float(r["price_month_usd"]), float(r["price_hour_usd"])
            self.assertGreater(month, 0)
            self.assertLess(month, 20000)
            self.assertAlmostEqual(month / hour, 730, delta=730 * 0.15)  # monthly is about 730 hours
            self.assertAlmostEqual(float(r["price_month_with_ipv4_usd"]),
                                   month + float(r["ipv4_extra_month_usd"]), places=3)

    def test_ipv4_extra_only_on_hetzner(self):
        for r in self.rows:
            if r["provider"] != "hetzner":
                self.assertEqual(float(r["ipv4_extra_month_usd"]), 0)

    def test_no_duplicate_plan_city(self):
        keys = [(r["provider"], r["plan"], r["region"]) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)))


class Summary(unittest.TestCase):
    def test_summary_matches_prices(self):
        rows = read("prices.csv")
        for s in read("summary.csv"):
            hits = [float(r["price_month_with_ipv4_usd"]) for r in rows
                    if r["provider"] == s["provider"] and r["plan"] == s["plan"]]
            self.assertEqual(len(hits), int(s["cities"]))
            self.assertAlmostEqual(min(hits), float(s["min_month_usd"]), places=2)
            self.assertAlmostEqual(max(hits), float(s["max_month_usd"]), places=2)
            self.assertLessEqual(float(s["min_month_usd"]), float(s["median_month_usd"]))
            self.assertLessEqual(float(s["median_month_usd"]), float(s["max_month_usd"]))


class Meta(unittest.TestCase):
    def test_meta(self):
        with open(os.path.join(DATA, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["rows"], len(read("prices.csv")))
        self.assertEqual(meta["skipped"], [])
        self.assertTrue(meta["collected_at"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
