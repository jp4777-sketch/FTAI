"""Monthly fleet telemetry (Operating Base, Cycles, Flight Miles) from OpenSky Trino.

Credentials come from the environment (OS_USER, OS_PASSWORD); load them from .env with:
    set -a; source .env; set +a
Usage:
    python fetch_opensky_data.py --describe          # sanity-check the table schemas first
    python fetch_opensky_data.py [--months 12]
"""
import argparse
import os
import sys
from datetime import date, timedelta

import pandas as pd
from trino.auth import BasicAuthentication
from trino.dbapi import connect

HOST, PORT = "trino.opensky-network.org", 443
CATALOG, SCHEMA = "minio", "osn"
# Table holding icao24 -> typecode. Override if your OpenSky schema names it differently.
AIRCRAFT_TABLE = os.environ.get("OS_AIRCRAFT_TABLE", "aircraft_database")
EARTH_RADIUS_MI = 3958.8

QUERY = f"""
WITH ac AS (
    SELECT lower(icao24) AS icao24,
           CASE WHEN upper(typecode) LIKE 'A320%' THEN 'A320'
                WHEN upper(typecode) IN ('B736','B737','B738','B739') THEN 'B737NG'
           END AS family
    FROM {AIRCRAFT_TABLE}
    WHERE upper(typecode) = 'A320'
       OR upper(typecode) IN ('B736','B737','B738','B739')
)
SELECT date_trunc('month', from_unixtime(f.day)) AS month,
       ac.family,
       COUNT(DISTINCT f.icao24) AS operating_base,
       COUNT(*) AS cycles,
       SUM({EARTH_RADIUS_MI} * 2 * asin(sqrt(
             power(sin(radians(f.estlatitude2 - f.estlatitude1) / 2), 2)
             + cos(radians(f.estlatitude1)) * cos(radians(f.estlatitude2))
               * power(sin(radians(f.estlongitude2 - f.estlongitude1) / 2), 2)
       ))) AS flight_miles
FROM flights_data4 f
JOIN ac ON lower(f.icao24) = ac.icao24
WHERE f.day >= {{start_ts}} AND f.day < {{end_ts}}      -- partition pruning on `day`
  AND f.estlatitude1 IS NOT NULL AND f.estlatitude2 IS NOT NULL
  AND f.estlongitude1 IS NOT NULL AND f.estlongitude2 IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2
"""


def connection():
    user, pw = os.environ.get("OS_USER"), os.environ.get("OS_PASSWORD")
    if not user or not pw:
        sys.exit("OS_USER / OS_PASSWORD not set. Fill in .env, then: set -a; source .env; set +a")
    return connect(host=HOST, port=PORT, http_scheme="https", user=user,
                   auth=BasicAuthentication(user, pw), catalog=CATALOG, schema=SCHEMA)


def describe(cur):
    for t in ("flights_data4", AIRCRAFT_TABLE):
        cur.execute(f"DESCRIBE {t}")
        print(f"--- {t}")
        for r in cur.fetchall():
            print(r[0], r[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--describe", action="store_true")
    ap.add_argument("--out", default="fleet_telemetry.csv")
    args = ap.parse_args()

    cur = connection().cursor()
    if args.describe:
        return describe(cur)

    # Whole months only: first of the month `months` ago -> first of the current month.
    end = date.today().replace(day=1)
    start = end
    for _ in range(args.months):
        start = (start - timedelta(days=1)).replace(day=1)
    to_ts = lambda d: int(pd.Timestamp(d, tz="UTC").timestamp())
    cur.execute(QUERY.format(start_ts=to_ts(start), end_ts=to_ts(end)))
    df = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows to {args.out}")


if __name__ == "__main__":
    main()
