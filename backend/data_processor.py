"""
data_processor.py - Data loading, cleaning, and feature engineering
for the Bengaluru Parking Violations dataset (~298K records).
"""

import pandas as pd
import numpy as np
import json
import re
import os


def load_data(filepath: str) -> pd.DataFrame:
    """Load the CSV dataset and perform initial cleaning."""
    print(f"[DataProcessor] Loading data from {filepath}...")
    df = pd.read_csv(filepath, low_memory=False)
    print(f"[DataProcessor] Loaded {len(df)} records with {len(df.columns)} columns.")
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and preprocess the raw dataframe."""
    print("[DataProcessor] Cleaning data...")

    # Drop rows with missing critical fields
    df = df.dropna(subset=["latitude", "longitude", "created_datetime", "violation_type"])

    # Parse datetime columns
    for col in ["created_datetime", "closed_datetime", "modified_datetime",
                 "action_taken_timestamp", "validation_timestamp",
                 "data_sent_to_scita_timestamp"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # Filter out invalid coordinates (must be in Bengaluru region)
    df = df[
        (df["latitude"] >= 12.7) & (df["latitude"] <= 13.2) &
        (df["longitude"] >= 77.3) & (df["longitude"] <= 77.9)
    ].copy()

    # Replace NULL strings with actual NaN
    df.replace("NULL", np.nan, inplace=True)

    print(f"[DataProcessor] After cleaning: {len(df)} records.")
    return df


def parse_violation_types(violation_str: str) -> list:
    """Parse the JSON-like violation type string into a list of violations."""
    if pd.isna(violation_str):
        return []
    try:
        # The data has format like: ["WRONG PARKING","PARKING NEAR ROAD CROSSING"]
        parsed = json.loads(violation_str)
        if isinstance(parsed, list):
            return [v.strip() for v in parsed if isinstance(v, str)]
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: try regex extraction
    matches = re.findall(r'"([^"]+)"', str(violation_str))
    return matches


def parse_offence_codes(code_str: str) -> list:
    """Parse the offence code string into a list of codes."""
    if pd.isna(code_str):
        return []
    try:
        parsed = json.loads(str(code_str))
        if isinstance(parsed, list):
            return [int(c) for c in parsed]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return []


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features for analysis and modeling."""
    print("[DataProcessor] Engineering features...")

    # Temporal features from created_datetime
    df["hour"] = df["created_datetime"].dt.hour
    df["day_of_week"] = df["created_datetime"].dt.dayofweek  # 0=Mon, 6=Sun
    df["day_name"] = df["created_datetime"].dt.day_name()
    df["month"] = df["created_datetime"].dt.month
    df["month_name"] = df["created_datetime"].dt.month_name()
    df["date"] = df["created_datetime"].dt.date
    week_series = df["created_datetime"].dt.isocalendar().week
    df["week"] = pd.to_numeric(week_series, errors="coerce").fillna(0).astype(int)

    # Time-of-day buckets
    def time_bucket(h):
        if 6 <= h < 10:
            return "Morning Rush"
        elif 10 <= h < 16:
            return "Midday"
        elif 16 <= h < 21:
            return "Evening Rush"
        else:
            return "Night"

    df["time_bucket"] = df["hour"].apply(time_bucket)

    # Is peak hour?
    df["is_peak_hour"] = df["hour"].apply(lambda h: 1 if (7 <= h <= 10) or (17 <= h <= 20) else 0)

    # Parse violation types into lists
    df["violation_list"] = df["violation_type"].apply(parse_violation_types)
    df["num_violations"] = df["violation_list"].apply(len)

    # Primary violation (first in the list)
    df["primary_violation"] = df["violation_list"].apply(
        lambda x: x[0] if len(x) > 0 else "UNKNOWN"
    )

    # Parse offence codes
    df["offence_code_list"] = df["offence_code"].apply(parse_offence_codes)

    # Vehicle type normalization
    vehicle_type_col = "updated_vehicle_type"
    if vehicle_type_col not in df.columns or df[vehicle_type_col].isna().all():
        vehicle_type_col = "vehicle_type"
    df["vehicle_category"] = df[vehicle_type_col].fillna(df["vehicle_type"]).fillna("UNKNOWN").str.upper().str.strip()

    # Map to broader categories
    vehicle_map = {
        "CAR": "4-Wheeler",
        "SEDAN": "4-Wheeler",
        "SUV": "4-Wheeler",
        "HATCHBACK": "4-Wheeler",
        "MAXI-CAB": "4-Wheeler",
        "JEEP": "4-Wheeler",
        "VAN": "4-Wheeler",
        "TAXI": "4-Wheeler",
        "SCOOTER": "2-Wheeler",
        "MOTORCYCLE": "2-Wheeler",
        "BIKE": "2-Wheeler",
        "MOPED": "2-Wheeler",
        "BUS": "Heavy Vehicle",
        "TRUCK": "Heavy Vehicle",
        "LORRY": "Heavy Vehicle",
        "TEMPO": "Heavy Vehicle",
        "MINI-BUS": "Heavy Vehicle",
        "AUTO RICKSHAW": "3-Wheeler",
        "AUTO": "3-Wheeler",
        "E-RICKSHAW": "3-Wheeler",
    }
    df["vehicle_broad_category"] = df["vehicle_category"].map(vehicle_map).fillna("Other")

    # Violation severity scoring
    severity_map = {
        "PARKING IN A MAIN ROAD": 5,
        "PARKING NEAR ROAD CROSSING": 5,
        "WRONG PARKING": 3,
        "NO PARKING": 4,
        "PARKING ON FOOTPATH": 4,
        "DOUBLE PARKING": 5,
        "PARKING AT BUS STOP": 5,
        "PARKING NEAR TRAFFIC SIGNAL": 5,
    }
    df["violation_severity"] = df["primary_violation"].map(
        lambda v: max([severity_map.get(vv.strip().upper(), 2) for vv in [v]] if v else [2])
    )

    # Vehicle congestion impact weight
    vehicle_weight = {
        "Heavy Vehicle": 3.0,
        "4-Wheeler": 2.0,
        "3-Wheeler": 1.5,
        "2-Wheeler": 1.0,
        "Other": 1.5,
    }
    df["vehicle_weight"] = df["vehicle_broad_category"].map(vehicle_weight).fillna(1.5)

    # Junction vs non-junction
    df["is_junction"] = df["junction_name"].apply(
        lambda x: 0 if pd.isna(x) or str(x).strip().lower() in ["no junction", "nan", ""] else 1
    )

    # Validation status
    df["is_validated"] = df["validation_status"].apply(
        lambda x: 1 if str(x).strip().lower() == "approved" else 0
    )

    # Has action been taken?
    df["action_taken"] = df["action_taken_timestamp"].notna().astype(int)

    print(f"[DataProcessor] Feature engineering complete. Columns: {len(df.columns)}")
    return df


def get_processed_data(filepath: str) -> pd.DataFrame:
    """Full pipeline: load -> clean -> engineer features."""
    df = load_data(filepath)
    df = clean_data(df)
    df = engineer_features(df)
    return df


if __name__ == "__main__":
    # Test the pipeline
    data_path = os.path.join(os.path.dirname(__file__), "..",
                             "jan to may police violation_anonymized791b166.csv")
    df = get_processed_data(data_path)
    print(f"\nProcessed dataset shape: {df.shape}")
    print(f"\nSample columns: {list(df.columns)}")
    print(f"\nViolation types found:")
    all_violations = []
    for vl in df["violation_list"]:
        all_violations.extend(vl)
    from collections import Counter
    for v, c in Counter(all_violations).most_common(15):
        print(f"  {v}: {c}")
    print(f"\nVehicle categories: {df['vehicle_broad_category'].value_counts().to_dict()}")
    print(f"\nPolice stations: {df['police_station'].nunique()} unique")
    print(f"Time range: {df['created_datetime'].min()} to {df['created_datetime'].max()}")
