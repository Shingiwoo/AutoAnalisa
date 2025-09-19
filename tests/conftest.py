import os
import pandas as pd


def load_csv_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # ensure dtypes
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True).dt.tz_convert("Asia/Jakarta")
    df["close_time"] = pd.to_datetime(df["close_time"], utc=True).dt.tz_convert("Asia/Jakarta")
    return df

