"""Merge static Installed Base with monthly telemetry; compute utilization metrics."""
import numpy as np
import pandas as pd

tele = pd.read_csv("fleet_telemetry.csv", parse_dates=["month"])
base = pd.read_csv("installed_base.csv")

df = tele.merge(base, on="family", how="left")
df["avg_stage_length_mi"] = df["flight_miles"] / df["cycles"].replace(0, np.nan)
df["asset_utilization"] = df["cycles"] / df["operating_base"].replace(0, np.nan)  # cycles/aircraft/month
df["operating_pct_of_installed"] = df["operating_base"] / df["installed_base"] * 100
df["parked_est"] = df["installed_base"] - df["operating_base"]
df["cycles_per_day"] = df["asset_utilization"] / df["month"].dt.days_in_month

cols = ["month", "family", "installed_base", "operating_base", "parked_est", "operating_pct_of_installed",
        "cycles", "flight_miles", "avg_stage_length_mi", "asset_utilization", "cycles_per_day"]
out = df[cols].sort_values(["family", "month"])
out.to_csv("fleet_performance.csv", index=False)
print(out.round(1).to_string(index=False))
