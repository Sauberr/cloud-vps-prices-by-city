# Cloud VPS prices by city

[![tests](https://github.com/Sauberr/cloud-vps-prices-by-city/actions/workflows/test.yml/badge.svg)](https://github.com/Sauberr/cloud-vps-prices-by-city/actions/workflows/test.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24541257.svg)](https://doi.org/10.5281/zenodo.24541257)
[![License: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

Public list prices of cloud VPS plans on **Vultr, DigitalOcean, Linode (Akamai) and Hetzner**, one row per plan and city, collected from each provider's own API. Plus a summary that puts the same shared-CPU size side by side on every provider.

- `data/prices.csv`: 4,015 rows, every plan in every city where it is sold (86 locations).
- `data/summary.csv`: the same sizes compared across providers.
- `data/meta.json`: when the data was collected and from what.
- `collect.py`: the script that produced it (Python 3, standard library only).

Collected on 25 November 2026. Browse it as a table: [neckrez.tech/data/cloud-vps-prices](https://neckrez.tech/data/cloud-vps-prices).

## The same server on four clouds

Monthly price in US dollars of a shared-CPU x86 VPS, including one public IPv4, the cheapest and the dearest city where each provider sells it:

| Size | Vultr | DigitalOcean | Linode | Hetzner |
|---|---|---|---|---|
| 1 vCPU, 1 GB | $5 | $6 | $5–7 | $6.59–9.59 |
| 2 vCPU, 4 GB | $20 | $24 | $24–33.60 | $7.09 |
| 4 vCPU, 8 GB | $40 | $48 | $48–67.20 | $10.59 |

What the numbers show:

- **Vultr and DigitalOcean charge the same in every city.** The city you pick does not change the price.
- **Linode charges more in some locations**, up to 40% more (for example São Paulo and Jakarta).
- **Hetzner is much cheaper for 2 vCPU and above**, but sells those sizes only in Germany and Finland, and the same plan can cost up to 45% more in one location than another (Singapore against Helsinki).
- **Included traffic differs a lot**: 1–5 TB a month on Vultr, DigitalOcean and Linode, 20 TB on Hetzner.

## Columns

`prices.csv`

| Column | Meaning |
|---|---|
| `provider` | vultr, digitalocean, linode, hetzner |
| `plan` | The provider's own plan id |
| `family` | The provider's name for the plan line (Cloud Compute, Basic, Shared CPU, Cost-Optimized…) |
| `cpu` | `shared` or `dedicated` vCPUs |
| `arch` | `x86` or `arm` |
| `vcpu`, `ram_gb`, `disk_gb` | Size |
| `transfer_tb` | Outbound traffic included per month, in TB as the provider advertises it |
| `region`, `city`, `country`, `continent` | Where it runs (country as ISO 3166-1 alpha-2) |
| `price_month_usd`, `price_hour_usd` | List price |
| `ipv4_extra_month_usd` | What a public IPv4 costs on top (Hetzner only; 0 elsewhere, where it is included) |
| `price_month_with_ipv4_usd` | Monthly price including one public IPv4: the column to compare |

`summary.csv`: for each size and provider, the cheapest plan of exactly that size (shared CPU, x86), how many cities sell it, and its minimum, median and maximum monthly price over those cities.

## How it was collected

`collect.py` calls each provider's public price list:

- Vultr: `GET /v2/plans`, `GET /v2/regions` (no key needed). One price per plan, everywhere it is offered.
- DigitalOcean: `GET /v2/sizes`, `GET /v2/regions` (a read token). One price per size, everywhere it is offered.
- Linode: `GET /v4/linode/types`, `GET /v4/regions` (no key needed). `region_prices` replaces the base price where a location costs more.
- Hetzner Cloud: `GET /v1/server_types`, `GET /v1/locations`, `GET /v1/pricing` (a read token). A price per location; the primary IPv4 price comes from `/v1/pricing`.

Left out: GPU plans, bare metal, free-tier plans, deprecated plans and anything the provider marks unavailable. Prices are without VAT or sales tax, in US dollars as the APIs return them.

Run it yourself:

```bash
DIGITALOCEAN_TOKEN=... HCLOUD_TOKEN=... python3 collect.py data/
```

Without a token, that provider is skipped and the skip is recorded in `meta.json`.

## Limits

- These are list prices. Discounts, credits, reserved pricing and taxes are not included.
- "Same size" means the same vCPU count and memory. Disk, traffic and CPU generation still differ; the columns say how.
- A plan listed in a city can still be out of stock there at a given moment.
- Prices change. The data will be refreshed, with each version tagged and archived on Zenodo; the DOI above always points to the latest version.

## Cite

Data: [CC BY 4.0](LICENSE). Use it for anything, including commercially, as long as you credit the source:

> Neckrez (2026). *Cloud VPS prices by city: Vultr, DigitalOcean, Linode and Hetzner* [Data set]. Zenodo. https://doi.org/10.5281/zenodo.24541257

GitHub's "Cite this repository" button gives the same in BibTeX and APA. The code (`collect.py`, tests) is MIT, see [LICENSE-CODE](LICENSE-CODE).

## About

Collected by [Neckrez](https://neckrez.tech), a crypto-paid cloud host that resells Vultr, DigitalOcean, Linode and Hetzner servers by the hour. The data comes straight from the providers' APIs and does not include our own prices.
