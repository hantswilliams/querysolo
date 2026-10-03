#!/usr/bin/env python3
# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Write a small, made-up dataset to try QuerySolo on: a folder of four CSV files that
exercise the app's screens (a folder drop, a group-by bar chart, a date line chart, a
join). Standard library only, seeded, so every run writes the same bytes; nothing here is
real. The repo keeps no data files (CLAUDE.md), so this script is what is committed.

    python3 examples/sample-data/make_sample.py            # ~/querysolo-demo/sample
    python3 examples/sample-data/make_sample.py ~/somewhere --orders 20000
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

REGIONS = ["north", "south", "east", "west", "central"]
PRODUCTS = [
    ("QuerySolo Mug", "goods", 14.00),
    ("Field Notebook", "goods", 9.50),
    ("Trail Map", "goods", 6.00),
    ("Canoe Rental (day)", "services", 48.00),
    ("Guided Walk", "services", 35.00),
    ("Cabin Night", "lodging", 120.00),
    ("Campsite Night", "lodging", 32.00),
    ("Firewood Bundle", "goods", 8.00),
    ("Fishing Permit", "services", 22.00),
    ("Kayak Rental (hour)", "services", 18.00),
    ("Rain Jacket", "goods", 79.00),
    ("Thermos", "goods", 27.00),
]
STATUSES = ["paid", "paid", "paid", "paid", "refunded", "pending"]
FIRST = ["Ann", "Bo", "Cy", "Dee", "Eli", "Fay", "Gus", "Ida", "Jo", "Kai", "Lou", "Mia", "Ned", "Ola", "Pat", "Quinn", "Rae", "Sam", "Tia", "Uma", "Val", "Wes", "Xi", "Yan", "Zed"]
LAST = ["Brook", "Field", "Glen", "Hill", "Lake", "Marsh", "Moor", "Pond", "Reed", "Shore", "Stone", "Vale", "Wood"]


def write(path: Path, header: list[str], rows) -> int:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        n = 0
        for row in rows:
            w.writerow(row)
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", nargs="?", default=str(Path.home() / "querysolo-demo" / "sample"))
    ap.add_argument("--orders", type=int, default=5000, help="rows in orders.csv (5,000 is about 500 KB)")
    ap.add_argument("--customers", type=int, default=200)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.folder).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    customers = []
    for i in range(1, args.customers + 1):
        customers.append(
            (
                f"C{i:04d}",
                f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                rng.choice(REGIONS),
                (date(2024, 1, 1) + timedelta(days=rng.randrange(0, 700))).isoformat(),
                rng.choice(["email", "walk-in", "referral", "search"]),
            )
        )
    n_customers = write(out / "customers.csv", ["customer_id", "name", "region", "joined", "source"], customers)

    n_products = write(
        out / "products.csv",
        ["product_id", "product", "category", "unit_price"],
        [(f"P{i:03d}", name, cat, f"{price:.2f}") for i, (name, cat, price) in enumerate(PRODUCTS, 1)],
    )

    start = date(2026, 1, 1)
    days = 250  # to early September 2026
    orders = []
    for i in range(1, args.orders + 1):
        d = start + timedelta(days=int(rng.triangular(0, days, days * 0.7)))  # busier lately
        pid = rng.randrange(len(PRODUCTS))
        name, cat, price = PRODUCTS[pid]
        qty = 1 if cat == "lodging" else rng.choice([1, 1, 1, 2, 2, 3, 4])
        if cat == "lodging":
            qty = rng.choice([1, 1, 2, 3])
        cust = customers[rng.randrange(len(customers))]
        amount = round(qty * price * (0.9 if rng.random() < 0.1 else 1.0), 2)
        orders.append(
            (
                f"O{i:06d}",
                d.isoformat(),
                f"{d.isoformat()}T{rng.randrange(7, 21):02d}:{rng.randrange(60):02d}:00",
                cust[0],
                cust[2],
                f"P{pid + 1:03d}",
                name,
                cat,
                qty,
                f"{price:.2f}",
                f"{amount:.2f}",
                rng.choice(STATUSES),
            )
        )
    orders.sort(key=lambda r: r[2])
    orders = [(f"O{i:06d}", *o[1:]) for i, o in enumerate(orders, 1)]  # ids in time order
    n_orders = write(
        out / "orders.csv",
        ["order_id", "order_date", "ordered_at", "customer_id", "region", "product_id", "product", "category", "quantity", "unit_price", "amount", "status"],
        orders,
    )

    by_day: dict[str, list[float]] = {}
    for o in orders:
        if o[11] == "paid":
            by_day.setdefault(o[1], []).append(float(o[10]))
    daily = []
    for k in range(days):
        d = (start + timedelta(days=k)).isoformat()
        amounts = by_day.get(d, [])
        daily.append((d, len(amounts), f"{sum(amounts):.2f}", f"{(sum(amounts) / len(amounts)) if amounts else 0:.2f}"))
    n_daily = write(out / "daily_sales.csv", ["day", "orders", "revenue", "avg_order"], daily)

    (out / "notes.txt").write_text("Made-up data from examples/sample-data/make_sample.py; not imported (not a data file).\n")
    size = sum(p.stat().st_size for p in out.glob("*.csv"))
    print(f"wrote {out}: customers.csv ({n_customers}), products.csv ({n_products}), orders.csv ({n_orders:,}), daily_sales.csv ({n_daily}); {size / 1024:.0f} KB of CSV")


if __name__ == "__main__":
    main()
