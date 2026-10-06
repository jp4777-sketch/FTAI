"""Download the OpenSky aircraft database and build the static Installed Base per month.

Writes aircraft_metadata_filtered.csv (one row per valid registration) and
installed_base.csv (family, installed_base). Pass --src to use a manually downloaded file.
"""
import argparse
import io
import sys
import urllib.request

import pandas as pd

URLS = [
    "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv",
    "https://s3.opensky-network.org/data-samples/metadata/aircraftDatabase.csv",
]
FAMILIES = {"A320": "A320", "B736": "B737NG", "B737": "B737NG", "B738": "B737NG", "B739": "B737NG"}


def download():
    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return io.BytesIO(r.read())
        except Exception as e:
            print(f"failed {url}: {e}", file=sys.stderr)
    sys.exit("Could not download metadata; download it manually and pass --src <file>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    args = ap.parse_args()
    df = pd.read_csv(args.src or download(), dtype=str, low_memory=False,
                     usecols=lambda c: c in {"icao24", "registration", "typecode", "built",
                                             "operator", "operatorIcao", "status"})
    df["typecode"] = df["typecode"].str.upper().str.strip()
    df = df[df["typecode"].isin(FAMILIES)].copy()
    df["family"] = df["typecode"].map(FAMILIES)
    # Valid = has a registration and an icao24; one row per airframe.
    df = df[df["registration"].notna() & df["icao24"].notna()]
    df["icao24"] = df["icao24"].str.lower()
    df = df.drop_duplicates("icao24")
    df.to_csv("aircraft_metadata_filtered.csv", index=False)
    base = df.groupby("family")["icao24"].nunique().rename("installed_base").reset_index()
    base.to_csv("installed_base.csv", index=False)
    print(base.to_string(index=False))


if __name__ == "__main__":
    main()
