"""
models.py - AI/ML models for parking intelligence:
  1. HDBSCAN spatial hotspot detection
  2. Congestion impact scoring
  3. Temporal pattern analysis
  4. Enforcement zone prioritization
"""

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import MinMaxScaler
from collections import Counter
import warnings

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# 1. Hotspot Detection using DBSCAN (density-based spatial clustering)
# ---------------------------------------------------------------------------

def detect_hotspots(df: pd.DataFrame, eps_km: float = 0.3, min_samples: int = 15) -> pd.DataFrame:
    """
    Use DBSCAN to identify spatial clusters of parking violations.
    eps_km: radius in km (~300m default)
    min_samples: minimum violations to form a cluster
    Returns a DataFrame of hotspot clusters with metadata.
    """
    print("[Models] Running spatial hotspot detection (DBSCAN)...")

    coords = df[["latitude", "longitude"]].values

    # Convert km to radians for haversine metric
    eps_rad = eps_km / 6371.0  # Earth radius in km

    clustering = DBSCAN(
        eps=eps_rad,
        min_samples=min_samples,
        metric="haversine",
        algorithm="ball_tree"
    )

    # DBSCAN with haversine expects radians
    coords_rad = np.radians(coords)
    labels = clustering.fit_predict(coords_rad)

    df = df.copy()
    df["cluster_id"] = labels

    # Filter out noise (label == -1)
    clustered = df[df["cluster_id"] != -1]
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    print(f"[Models] Found {n_clusters} hotspot clusters ({len(clustered)} violations in clusters).")

    # Build hotspot summaries
    hotspots = []
    for cid in sorted(clustered["cluster_id"].unique()):
        cluster_data = clustered[clustered["cluster_id"] == cid]

        # Get representative location name
        location_counts = cluster_data["location"].value_counts()
        top_location = location_counts.index[0] if len(location_counts) > 0 else "Unknown"

        # Get police station
        station_counts = cluster_data["police_station"].value_counts()
        top_station = station_counts.index[0] if len(station_counts) > 0 else "Unknown"

        # Violation type breakdown
        all_violations = []
        for vl in cluster_data["violation_list"]:
            all_violations.extend(vl)
        violation_breakdown = dict(Counter(all_violations).most_common(5))

        # Vehicle breakdown
        vehicle_breakdown = cluster_data["vehicle_broad_category"].value_counts().to_dict()

        # Temporal patterns
        peak_hours = cluster_data["hour"].value_counts().head(3).index.tolist()
        peak_days = cluster_data["day_name"].value_counts().head(3).index.tolist()

        hotspot = {
            "cluster_id": int(cid),
            "center_lat": float(cluster_data["latitude"].mean()),
            "center_lng": float(cluster_data["longitude"].mean()),
            "violation_count": int(len(cluster_data)),
            "unique_vehicles": int(cluster_data["vehicle_number"].nunique()),
            "top_location": str(top_location)[:100],
            "police_station": str(top_station),
            "violation_breakdown": violation_breakdown,
            "vehicle_breakdown": vehicle_breakdown,
            "peak_hours": peak_hours,
            "peak_days": peak_days,
            "avg_severity": float(cluster_data["violation_severity"].mean()),
            "junction_pct": float(cluster_data["is_junction"].mean() * 100),
            "validated_pct": float(cluster_data["is_validated"].mean() * 100),
            "radius_m": float(_cluster_radius_meters(cluster_data)),
        }
        hotspots.append(hotspot)

    return pd.DataFrame(hotspots), df


def _cluster_radius_meters(cluster_data: pd.DataFrame) -> float:
    """Calculate approximate radius of cluster in meters."""
    center_lat = cluster_data["latitude"].mean()
    center_lng = cluster_data["longitude"].mean()
    # Approximate distance from center to furthest point
    lat_diff = (cluster_data["latitude"] - center_lat).abs().max()
    lng_diff = (cluster_data["longitude"] - center_lng).abs().max()
    # Rough conversion: 1 degree lat ≈ 111km, 1 degree lng ≈ 85km at Bengaluru latitude
    radius = max(lat_diff * 111000, lng_diff * 85000)
    return min(radius, 5000)  # Cap at 5km


# ---------------------------------------------------------------------------
# 2. Congestion Impact Score
# ---------------------------------------------------------------------------

def compute_congestion_impact(hotspots_df: pd.DataFrame, df_clustered: pd.DataFrame) -> pd.DataFrame:
    """
    Compute a composite Congestion Impact Score (0-100) for each hotspot.
    Factors:
      - Violation density (count per area)
      - Average violation severity
      - Vehicle weight impact
      - Peak hour concentration
      - Junction proximity
      - Repeat offender ratio
    """
    print("[Models] Computing congestion impact scores...")

    if hotspots_df.empty:
        return hotspots_df

    scores = []
    for _, hotspot in hotspots_df.iterrows():
        cid = hotspot["cluster_id"]
        cluster_data = df_clustered[df_clustered["cluster_id"] == cid]

        # Factor 1: Violation density (violations per 100m radius)
        radius = max(hotspot.get("radius_m", 100), 50)
        area = np.pi * (radius ** 2)  # m²
        density = len(cluster_data) / (area / 10000)  # per 100m²
        density_score = min(density * 10, 100)

        # Factor 2: Severity score
        severity_score = (hotspot["avg_severity"] / 5.0) * 100

        # Factor 3: Vehicle congestion weight
        avg_vehicle_weight = cluster_data["vehicle_weight"].mean()
        vehicle_score = (avg_vehicle_weight / 3.0) * 100

        # Factor 4: Peak hour concentration
        peak_hour_pct = cluster_data["is_peak_hour"].mean() * 100
        peak_score = peak_hour_pct

        # Factor 5: Junction impact
        junction_score = hotspot["junction_pct"]

        # Factor 6: Volume score (normalized by max cluster)
        max_count = hotspots_df["violation_count"].max()
        volume_score = (hotspot["violation_count"] / max_count) * 100 if max_count > 0 else 0

        # Weighted composite
        impact_score = (
            density_score * 0.20 +
            severity_score * 0.20 +
            vehicle_score * 0.10 +
            peak_score * 0.20 +
            junction_score * 0.10 +
            volume_score * 0.20
        )

        scores.append(round(min(impact_score, 100), 1))

    hotspots_df = hotspots_df.copy()
    hotspots_df["congestion_impact_score"] = scores

    # Classify impact level
    def impact_level(score):
        if score >= 70:
            return "Critical"
        elif score >= 50:
            return "High"
        elif score >= 30:
            return "Moderate"
        else:
            return "Low"

    hotspots_df["impact_level"] = hotspots_df["congestion_impact_score"].apply(impact_level)

    # Rank by impact
    hotspots_df = hotspots_df.sort_values("congestion_impact_score", ascending=False).reset_index(drop=True)
    hotspots_df["rank"] = range(1, len(hotspots_df) + 1)

    print(f"[Models] Impact scores computed. Critical: {(hotspots_df['impact_level']=='Critical').sum()}, "
          f"High: {(hotspots_df['impact_level']=='High').sum()}, "
          f"Moderate: {(hotspots_df['impact_level']=='Moderate').sum()}, "
          f"Low: {(hotspots_df['impact_level']=='Low').sum()}")

    return hotspots_df


# ---------------------------------------------------------------------------
# 3. Temporal Pattern Analysis
# ---------------------------------------------------------------------------

def analyze_temporal_patterns(df: pd.DataFrame) -> dict:
    """Analyze temporal violation patterns for insights."""
    print("[Models] Analyzing temporal patterns...")

    results = {}

    # Hourly distribution
    hourly = df.groupby("hour").agg(
        count=("id", "count"),
        avg_severity=("violation_severity", "mean"),
    ).reset_index()
    results["hourly"] = hourly.to_dict(orient="records")

    # Day of week distribution
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily = df.groupby("day_name").agg(
        count=("id", "count"),
        avg_severity=("violation_severity", "mean"),
    ).reset_index()
    daily["day_name"] = pd.Categorical(daily["day_name"], categories=day_order, ordered=True)
    daily = daily.sort_values("day_name")
    results["daily"] = daily.to_dict(orient="records")

    # Monthly trend
    monthly = df.groupby("month_name").agg(
        count=("id", "count"),
        month_num=("month", "first"),
    ).reset_index()
    monthly = monthly.sort_values("month_num")
    results["monthly"] = monthly.to_dict(orient="records")

    # Time bucket distribution
    bucket_order = ["Morning Rush", "Midday", "Evening Rush", "Night"]
    bucket = df.groupby("time_bucket").agg(
        count=("id", "count"),
        avg_severity=("violation_severity", "mean"),
        peak_pct=("is_peak_hour", "mean"),
    ).reset_index()
    bucket["time_bucket"] = pd.Categorical(bucket["time_bucket"], categories=bucket_order, ordered=True)
    bucket = bucket.sort_values("time_bucket")
    results["time_buckets"] = bucket.to_dict(orient="records")

    # Weekly trend (violations per week)
    weekly = df.groupby("week").agg(count=("id", "count")).reset_index()
    weekly = weekly.sort_values("week")
    results["weekly"] = weekly.to_dict(orient="records")

    # Heatmap data: hour x day_of_week
    heatmap_data = df.groupby(["day_of_week", "hour"]).size().reset_index(name="count")
    results["hour_day_heatmap"] = heatmap_data.to_dict(orient="records")

    return results


# ---------------------------------------------------------------------------
# 4. Enforcement Prioritization
# ---------------------------------------------------------------------------

def prioritize_enforcement_zones(hotspots_df: pd.DataFrame, df_clustered: pd.DataFrame) -> pd.DataFrame:
    """
    Rank enforcement zones combining congestion impact with enforcement efficiency factors.
    """
    print("[Models] Computing enforcement priorities...")

    if hotspots_df.empty:
        return hotspots_df

    enforcement_scores = []
    for _, hotspot in hotspots_df.iterrows():
        cid = hotspot["cluster_id"]
        cluster_data = df_clustered[df_clustered["cluster_id"] == cid]

        # Base: congestion impact
        base_score = hotspot.get("congestion_impact_score", 50)

        # Enforcement gap: low action rate = higher priority
        action_rate = cluster_data["action_taken"].mean()
        enforcement_gap = (1 - action_rate) * 30  # 0-30 bonus

        # Recency: more recent violations = higher priority
        max_date = cluster_data["created_datetime"].max()
        min_date = cluster_data["created_datetime"].min()
        if pd.notna(max_date) and pd.notna(min_date):
            days_span = (max_date - min_date).days
            if days_span > 0:
                # Violations per day
                daily_rate = len(cluster_data) / days_span
                recency_score = min(daily_rate * 5, 20)  # 0-20 bonus
            else:
                recency_score = 10
        else:
            recency_score = 0

        # Repeat offender factor
        total_violations = len(cluster_data)
        unique_vehicles = cluster_data["vehicle_number"].nunique()
        if unique_vehicles > 0:
            repeat_ratio = total_violations / unique_vehicles
            repeat_score = min(repeat_ratio * 5, 15)  # 0-15 bonus
        else:
            repeat_score = 0

        final_score = min(base_score + enforcement_gap + recency_score + repeat_score, 100)
        enforcement_scores.append(round(final_score, 1))

    hotspots_df = hotspots_df.copy()
    hotspots_df["enforcement_priority_score"] = enforcement_scores

    # Priority level
    def priority_level(score):
        if score >= 75:
            return "Urgent"
        elif score >= 55:
            return "High"
        elif score >= 35:
            return "Medium"
        else:
            return "Low"

    hotspots_df["enforcement_priority"] = hotspots_df["enforcement_priority_score"].apply(priority_level)
    hotspots_df = hotspots_df.sort_values("enforcement_priority_score", ascending=False).reset_index(drop=True)
    hotspots_df["enforcement_rank"] = range(1, len(hotspots_df) + 1)

    print(f"[Models] Enforcement priorities set. Urgent: {(hotspots_df['enforcement_priority']=='Urgent').sum()}")

    return hotspots_df


# ---------------------------------------------------------------------------
# 5. Station-level Analytics
# ---------------------------------------------------------------------------

def analyze_by_station(df: pd.DataFrame) -> list:
    """Compute per-police-station analytics."""
    print("[Models] Computing station-level analytics...")

    stations = []
    for station, sdf in df.groupby("police_station"):
        if pd.isna(station):
            continue

        all_violations = []
        for vl in sdf["violation_list"]:
            all_violations.extend(vl)

        stations.append({
            "station": str(station),
            "total_violations": int(len(sdf)),
            "unique_vehicles": int(sdf["vehicle_number"].nunique()),
            "avg_severity": round(float(sdf["violation_severity"].mean()), 2),
            "peak_hour_pct": round(float(sdf["is_peak_hour"].mean() * 100), 1),
            "junction_pct": round(float(sdf["is_junction"].mean() * 100), 1),
            "action_rate": round(float(sdf["action_taken"].mean() * 100), 1),
            "validated_pct": round(float(sdf["is_validated"].mean() * 100), 1),
            "top_violation": Counter(all_violations).most_common(1)[0][0] if all_violations else "N/A",
            "top_vehicle": sdf["vehicle_broad_category"].value_counts().index[0] if len(sdf) > 0 else "N/A",
            "center_lat": round(float(sdf["latitude"].mean()), 6),
            "center_lng": round(float(sdf["longitude"].mean()), 6),
        })

    stations.sort(key=lambda x: x["total_violations"], reverse=True)
    return stations


# ---------------------------------------------------------------------------
# 6. Geospatial Heatmap Data
# ---------------------------------------------------------------------------

def generate_heatmap_data(df: pd.DataFrame, sample_size: int = 50000) -> list:
    """Generate lat/lng/intensity data for heatmap visualization."""
    print("[Models] Generating heatmap data...")

    if len(df) > sample_size:
        sample = df.sample(n=sample_size, random_state=42)
    else:
        sample = df

    heatmap = []
    for _, row in sample.iterrows():
        intensity = row.get("violation_severity", 3) * row.get("vehicle_weight", 1.5)
        heatmap.append([
            round(float(row["latitude"]), 6),
            round(float(row["longitude"]), 6),
            round(float(intensity), 2)
        ])

    print(f"[Models] Heatmap data: {len(heatmap)} points.")
    return heatmap


# ---------------------------------------------------------------------------
# 7. Summary Statistics
# ---------------------------------------------------------------------------

def compute_summary_stats(df: pd.DataFrame, hotspots_df: pd.DataFrame) -> dict:
    """Compute dashboard KPI summary statistics."""
    print("[Models] Computing summary statistics...")

    all_violations = []
    for vl in df["violation_list"]:
        all_violations.extend(vl)
    violation_counts = Counter(all_violations)

    # Top violation hours
    hourly_counts = df["hour"].value_counts().sort_index()
    peak_hour = int(hourly_counts.idxmax())

    stats = {
        "total_violations": int(len(df)),
        "unique_vehicles": int(df["vehicle_number"].nunique()),
        "total_hotspots": int(len(hotspots_df)) if not hotspots_df.empty else 0,
        "critical_hotspots": int((hotspots_df["impact_level"] == "Critical").sum()) if not hotspots_df.empty else 0,
        "high_hotspots": int((hotspots_df["impact_level"] == "High").sum()) if not hotspots_df.empty else 0,
        "police_stations": int(df["police_station"].nunique()),
        "peak_hour": peak_hour,
        "peak_hour_label": f"{peak_hour:02d}:00 - {(peak_hour+1)%24:02d}:00",
        "peak_day": df["day_name"].value_counts().index[0],
        "avg_daily_violations": round(float(len(df) / max(df["date"].nunique(), 1)), 1),
        "top_violations": dict(violation_counts.most_common(5)),
        "vehicle_distribution": df["vehicle_broad_category"].value_counts().to_dict(),
        "validation_rate": round(float(df["is_validated"].mean() * 100), 1),
        "action_rate": round(float(df["action_taken"].mean() * 100), 1),
        "junction_violation_pct": round(float(df["is_junction"].mean() * 100), 1),
        "avg_congestion_score": round(float(hotspots_df["congestion_impact_score"].mean()), 1) if not hotspots_df.empty else 0,
        "date_range": {
            "start": str(df["created_datetime"].min().date()) if not df.empty else "",
            "end": str(df["created_datetime"].max().date()) if not df.empty else "",
        }
    }

    return stats
