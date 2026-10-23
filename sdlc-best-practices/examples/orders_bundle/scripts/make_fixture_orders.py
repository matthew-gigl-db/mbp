"""Generate a small, valid batch of orders (JSON Lines) dated relative to today.

Used by CI/CD to seed the landing volume of a test environment before running the
orders_refresh job as an integration test. Dates are relative so the quality gate's
freshness rule passes on any day the pipeline runs.

    python scripts/make_fixture_orders.py /tmp/orders.json --rows 200
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone

STATUSES = ("PLACED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED")


def make_orders(rows: int, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    orders = []
    for i in range(rows):
        ts = now - timedelta(days=i % 3, minutes=rng.randint(0, 600))
        orders.append({
            "order_id": f"O-{now:%Y%m%d}-{i:06d}",
            "customer_id": f"C-{rng.randint(1, 50):04d}",
            "status": rng.choice(STATUSES),
            "amount": round(rng.uniform(5, 500), 2),
            "order_ts": ts.isoformat(),
        })
    return orders


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--rows", type=int, default=200)
    args = ap.parse_args()
    with open(args.output, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(order) + "\n" for order in make_orders(args.rows))
    print(f"wrote {args.rows} orders to {args.output}")


if __name__ == "__main__":
    main()
