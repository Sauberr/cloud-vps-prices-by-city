#!/usr/bin/env python3
"""Collect public list prices of cloud VPS plans on Vultr, DigitalOcean, Linode and Hetzner,
per plan and per city, from each provider's own API.

    python3 collect.py data/

Standard library only. Vultr and Linode price lists are public. DigitalOcean and Hetzner need
a read token from a free account: DIGITALOCEAN_TOKEN and HCLOUD_TOKEN (the script also accepts
DIGITALOCEAN_API_KEY and HETZNER_API_KEY). A provider without a token is skipped and noted in
meta.json.

Writes:
  prices.csv   one row per plan and city where the provider sells it
  summary.csv  the same shared-CPU x86 sizes compared across providers
  meta.json    when, from where, how many rows, which providers were skipped
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "cloud-vps-prices-by-city/1.0 (+https://github.com/Sauberr/cloud-vps-prices-by-city)"}
HOURS_PER_MONTH = 730

CONTINENT = {
    **dict.fromkeys(["US", "CA", "MX"], "North America"),
    **dict.fromkeys(["BR", "CL", "AR", "CO"], "South America"),
    **dict.fromkeys(["GB", "DE", "NL", "FR", "ES", "IT", "PL", "SE", "FI", "IE", "CH", "AT", "BE", "PT", "NO", "DK", "LT"], "Europe"),
    **dict.fromkeys(["JP", "KR", "SG", "IN", "ID", "HK", "TW", "MY", "TH"], "Asia"),
    **dict.fromkeys(["AU", "NZ"], "Oceania"),
    **dict.fromkeys(["ZA"], "Africa"),
    **dict.fromkeys(["IL", "AE"], "Middle East"),
}

# DigitalOcean regions carry only a name like "New York 1"; the country comes from here.
DO_COUNTRY = {"nyc": "US", "sfo": "US", "atl": "US", "ric": "US", "mkc": "US", "mem": "US", "tor": "CA", "ams": "NL", "lon": "GB",
              "fra": "DE", "sgp": "SG", "blr": "IN", "syd": "AU"}

FIELDS = ["provider", "plan", "family", "cpu", "arch", "vcpu", "ram_gb", "disk_gb", "transfer_tb",
          "region", "city", "country", "continent", "price_month_usd", "price_hour_usd",
          "ipv4_extra_month_usd", "price_month_with_ipv4_usd"]


def get(url: str, token: str = "") -> dict:
    headers = dict(UA)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as r:
                return json.load(r)
        except Exception:  # noqa: BLE001 — retry transient errors, then give up loudly
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def row(provider, plan, family, cpu, arch, vcpu, ram_gb, disk_gb, transfer_tb, region, city, country,
        month, hour=None, ipv4=0.0) -> dict:
    month = round(float(month), 4)
    hour = round(float(hour), 6) if hour else round(month / HOURS_PER_MONTH, 6)
    return {
        "provider": provider, "plan": plan, "family": family, "cpu": cpu, "arch": arch,
        "vcpu": int(vcpu), "ram_gb": round(float(ram_gb), 2), "disk_gb": int(disk_gb or 0),
        "transfer_tb": round(float(transfer_tb or 0), 2),
        "region": region, "city": city, "country": country, "continent": CONTINENT.get(country, ""),
        "price_month_usd": month, "price_hour_usd": hour,
        "ipv4_extra_month_usd": round(ipv4, 4), "price_month_with_ipv4_usd": round(month + ipv4, 4),
    }


# ── Vultr: public /v2/plans and /v2/regions; one price everywhere the plan is offered ─────────
VULTR_FAMILY = {"vc2": ("Cloud Compute", "shared"), "vhf": ("High Frequency", "shared"),
                "vhp": ("High Performance", "shared"), "voc": ("Optimized Cloud", "dedicated"),
                "vdc": ("Dedicated Cloud", "dedicated")}


def vultr() -> list[dict]:
    regions = {r["id"]: r for r in get("https://api.vultr.com/v2/regions?per_page=500")["regions"]}
    out = []
    for p in get("https://api.vultr.com/v2/plans?type=all&per_page=500")["plans"]:
        prefix = p["id"].split("-")[0]
        if prefix not in VULTR_FAMILY:
            continue  # GPU (vcg) and anything new we do not classify
        family, cpu = VULTR_FAMILY[prefix]
        arch = "arm" if "arm" in p["id"] else "x86"
        for loc in p.get("locations", []):
            r = regions.get(loc)
            if not r:
                continue
            out.append(row("vultr", p["id"], family, cpu, arch, p["vcpu_count"], p["ram"] / 1024, p["disk"],
                           p.get("bandwidth", 0) / 1024, loc, r["city"], r["country"], p["monthly_cost"],
                           p.get("hourly_cost")))
    return out


# ── DigitalOcean: /v2/sizes and /v2/regions (token); one price everywhere ─────────────────────
def do_family(slug: str, desc: str) -> tuple[str, str] | None:
    if slug.startswith("gpu"):
        return None
    if slug.startswith(("s-", "s5-")) or "shared" in desc.lower() or desc.lower().startswith("basic"):
        return (desc or "Basic", "shared")
    return (desc or "Dedicated", "dedicated")


def digitalocean(token: str) -> list[dict]:
    regions = {r["slug"]: r for r in get("https://api.digitalocean.com/v2/regions?per_page=200", token)["regions"]}
    out = []
    for s in get("https://api.digitalocean.com/v2/sizes?per_page=200", token)["sizes"]:
        fam = do_family(s["slug"], s.get("description", ""))
        if not fam or not s.get("available", True):
            continue
        for slug in s.get("regions", []):
            r = regions.get(slug)
            if not r or not r.get("available", True):
                continue
            country = DO_COUNTRY.get(slug[:3], "")
            if not country:
                print(f"digitalocean: unknown region {slug} ({r['name']}): add it to DO_COUNTRY", file=sys.stderr)
            city = r["name"].rstrip("0123456789 ").strip()
            out.append(row("digitalocean", s["slug"], fam[0], fam[1], "x86", s["vcpus"], s["memory"] / 1024, s["disk"],
                           s.get("transfer", 0), slug, city, country, s["price_monthly"], s.get("price_hourly")))
    return out


# ── Linode (Akamai): public /v4/linode/types and /v4/regions; some regions cost more ──────────
LINODE_CLASS = {"nanode": ("Shared CPU", "shared"), "standard": ("Shared CPU", "shared"),
                "dedicated": ("Dedicated CPU", "dedicated"), "highmem": ("High Memory", "dedicated"),
                "premium": ("Premium", "dedicated")}


def linode() -> list[dict]:
    regions = [r for r in get("https://api.linode.com/v4/regions?page_size=500")["data"]
               if r.get("status") == "ok" and "Linodes" in (r.get("capabilities") or [])]
    out = []
    for t in get("https://api.linode.com/v4/linode/types?page_size=500")["data"]:
        if t["class"] not in LINODE_CLASS:
            continue  # GPU, accelerated
        family, cpu = LINODE_CLASS[t["class"]]
        special = {rp["id"]: rp for rp in t.get("region_prices") or []}
        for r in regions:
            if t["class"] == "premium" and "Premium Plans" not in (r.get("capabilities") or []):
                continue
            price = special.get(r["id"]) or t["price"]
            if price.get("monthly") is None:
                continue  # hourly-only or not sold there
            city = r["label"].split(",")[0].strip()
            out.append(row("linode", t["id"], family, cpu, "x86", t["vcpus"], t["memory"] / 1024, t["disk"] / 1024,
                           t.get("transfer", 0) / 1000, r["id"], city, (r.get("country") or "").upper(),
                           price["monthly"], price.get("hourly")))
    return out


# ── Hetzner Cloud: /v1/server_types, /v1/locations, /v1/pricing (token); price per location ───
def hetzner(token: str) -> list[dict]:
    locations = {loc["name"]: loc for loc in get("https://api.hetzner.cloud/v1/locations", token)["locations"]}
    pricing = get("https://api.hetzner.cloud/v1/pricing", token)["pricing"]
    if pricing.get("currency", "USD") != "USD":
        raise RuntimeError(f"Hetzner prices are in {pricing.get('currency')}, not USD")
    ipv4 = {}
    for item in pricing.get("primary_ips", []):
        if item.get("type") == "ipv4":
            for pr in item.get("prices", []):
                ipv4[pr["location"]] = float(pr["price_monthly"]["net"])
    out = []
    types = get("https://api.hetzner.cloud/v1/server_types?per_page=50", token)["server_types"]
    for t in types:
        if t.get("deprecated") or (t.get("deprecation") or {}).get("unavailable_after"):
            continue
        cpu = t.get("cpu_type", "shared")
        family = {"cx": "Cost-Optimized", "cpx": "Regular Performance", "cax": "Arm64", "ccx": "General Purpose"}.get(
            "".join(ch for ch in t["name"] if ch.isalpha()), t["name"])
        for pr in t.get("prices", []):
            loc = locations.get(pr["location"])
            if not loc:
                continue
            traffic = (pr.get("included_traffic") or 0) / 2**40  # Hetzner counts in TiB ("20 TB")
            out.append(row("hetzner", t["name"], family, cpu, "arm" if t.get("architecture") == "arm" else "x86",
                           t["cores"], t["memory"], t["disk"], traffic, pr["location"], loc["city"], loc["country"],
                           pr["price_monthly"]["net"], pr["price_hourly"]["net"], ipv4.get(pr["location"], 0.0)))
    return out


# ── summary: the same shared-CPU x86 size on each provider ────────────────────────────────────
SIZES = [(1, 1), (1, 2), (2, 2), (2, 4), (4, 8), (8, 16), (16, 32)]


def summary(rows: list[dict]) -> list[dict]:
    out = []
    for vcpu, ram in SIZES:
        for provider in sorted({r["provider"] for r in rows}):
            hits = [r for r in rows if r["provider"] == provider and r["cpu"] == "shared" and r["arch"] == "x86"
                    and r["vcpu"] == vcpu and abs(r["ram_gb"] - ram) < 0.01]
            if not hits:
                continue
            # The cheapest plan of that size (a provider can sell several), then its spread over cities.
            best_plan = min(hits, key=lambda r: r["price_month_with_ipv4_usd"])["plan"]
            plan_rows = [r for r in hits if r["plan"] == best_plan]
            prices = [r["price_month_with_ipv4_usd"] for r in plan_rows]
            cheapest = min(plan_rows, key=lambda r: r["price_month_with_ipv4_usd"])
            out.append({
                "vcpu": vcpu, "ram_gb": ram, "provider": provider, "plan": best_plan,
                "disk_gb": cheapest["disk_gb"], "transfer_tb": cheapest["transfer_tb"],
                "cities": len(plan_rows),
                "min_month_usd": round(min(prices), 2), "median_month_usd": round(statistics.median(prices), 2),
                "max_month_usd": round(max(prices), 2),
                "cheapest_city": ("same everywhere" if min(prices) == max(prices)
                                  else cheapest["city"] if prices.count(min(prices)) == 1
                                  else f"{prices.count(min(prices))} cities"),
            })
    return out


def write_csv(path: str, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    do_token = os.environ.get("DIGITALOCEAN_TOKEN") or os.environ.get("DIGITALOCEAN_API_KEY", "")
    hz_token = os.environ.get("HCLOUD_TOKEN") or os.environ.get("HETZNER_API_KEY", "")
    rows, skipped = [], []
    for name, fn in (("vultr", vultr), ("digitalocean", lambda: digitalocean(do_token)),
                     ("linode", linode), ("hetzner", lambda: hetzner(hz_token))):
        if (name == "digitalocean" and not do_token) or (name == "hetzner" and not hz_token):
            skipped.append(f"{name}: no token")
            continue
        try:
            got = fn()
            rows += got
            print(f"{name}: {len(got)} rows", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"{name}: {exc}")
            print(f"{name}: FAILED {exc}", file=sys.stderr)
    rows = [r for r in rows if r["price_month_usd"] > 0]  # free-tier plans (Vultr's 0.5 GB) are not a price
    rows.sort(key=lambda r: (r["provider"], r["cpu"], r["vcpu"], r["ram_gb"], r["plan"], r["country"], r["city"]))
    write_csv(os.path.join(out_dir, "prices.csv"), rows, FIELDS)
    summ = summary(rows)
    write_csv(os.path.join(out_dir, "summary.csv"), summ, list(summ[0].keys()) if summ else ["vcpu"])
    meta = {
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": len(rows),
        "providers": {p: sum(1 for r in rows if r["provider"] == p) for p in sorted({r["provider"] for r in rows})},
        "cities": len({(r["provider"], r["region"]) for r in rows}),
        "skipped": skipped,
        "notes": [
            "Prices are the providers' public list prices in US dollars, without VAT or sales tax.",
            "Hetzner bills a primary IPv4 separately: ipv4_extra_month_usd holds it, and price_month_with_ipv4_usd "
            "adds it so every provider's price includes one public IPv4.",
            "Vultr and DigitalOcean charge the same everywhere a plan is offered; Linode and Hetzner price some "
            "locations higher.",
            "GPU, bare metal, free-tier and deprecated plans are left out.",
        ],
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data")
