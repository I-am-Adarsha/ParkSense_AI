"""
precompute.py - Pre-compute all analytics into JSON files
for fast, reliable frontend consumption.
"""

import json
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(__file__))

from data_processor import get_processed_data
from models import (
    detect_hotspots,
    compute_congestion_impact,
    analyze_temporal_patterns,
    prioritize_enforcement_zones,
    analyze_by_station,
    generate_heatmap_data,
    compute_summary_stats,
)


def main():
    # Paths
    data_path = os.path.join(
        os.path.dirname(__file__), "..",
        "jan to may police violation_anonymized791b166.csv"
    )
    output_dir = os.path.join(os.path.dirname(__file__), "precomputed")
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Load and process data
    print("=" * 60)
    print("STEP 1: Loading and processing data...")
    print("=" * 60)
    df = get_processed_data(data_path)

    # Step 2: Detect hotspots
    print("\n" + "=" * 60)
    print("STEP 2: Detecting hotspots...")
    print("=" * 60)
    hotspots_df, df_clustered = detect_hotspots(df, eps_km=0.3, min_samples=15)

    # Step 3: Compute congestion impact
    print("\n" + "=" * 60)
    print("STEP 3: Computing congestion impact scores...")
    print("=" * 60)
    hotspots_df = compute_congestion_impact(hotspots_df, df_clustered)

    # Step 4: Enforcement prioritization
    print("\n" + "=" * 60)
    print("STEP 4: Computing enforcement priorities...")
    print("=" * 60)
    hotspots_df = prioritize_enforcement_zones(hotspots_df, df_clustered)

    # Step 5: Temporal analysis
    print("\n" + "=" * 60)
    print("STEP 5: Analyzing temporal patterns...")
    print("=" * 60)
    temporal = analyze_temporal_patterns(df)

    # Step 6: Station analytics
    print("\n" + "=" * 60)
    print("STEP 6: Computing station analytics...")
    print("=" * 60)
    stations = analyze_by_station(df)

    # Step 7: Heatmap data
    print("\n" + "=" * 60)
    print("STEP 7: Generating heatmap data...")
    print("=" * 60)
    heatmap = generate_heatmap_data(df, sample_size=50000)

    # Step 8: Summary stats
    print("\n" + "=" * 60)
    print("STEP 8: Computing summary statistics...")
    print("=" * 60)
    stats = compute_summary_stats(df, hotspots_df)

    # Step 9: Vehicle analysis
    print("\n" + "=" * 60)
    print("STEP 9: Vehicle analysis...")
    print("=" * 60)
    vehicle_analysis = {
        "by_category": df["vehicle_broad_category"].value_counts().to_dict(),
        "by_type": df["vehicle_category"].value_counts().head(15).to_dict(),
        "severity_by_vehicle": df.groupby("vehicle_broad_category")["violation_severity"].mean().to_dict(),
        "peak_hour_by_vehicle": df.groupby("vehicle_broad_category")["is_peak_hour"].mean().to_dict(),
    }

    # Step 10: Violation type analysis
    print("\n" + "=" * 60)
    print("STEP 10: Violation type analysis...")
    print("=" * 60)
    all_violations = []
    for vl in df["violation_list"]:
        all_violations.extend(vl)
    from collections import Counter
    violation_counter = Counter(all_violations)

    violation_analysis = {
        "by_type": dict(violation_counter.most_common(20)),
        "by_station": {},
    }
    # Violations per station
    for station, sdf in df.groupby("police_station"):
        station_violations = []
        for vl in sdf["violation_list"]:
            station_violations.extend(vl)
        violation_analysis["by_station"][str(station)] = dict(Counter(station_violations).most_common(5))

    # --- Save all outputs ---
    print("\n" + "=" * 60)
    print("SAVING OUTPUTS...")
    print("=" * 60)

    def save_json(data, filename):
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str, ensure_ascii=False)
        size = os.path.getsize(filepath) / 1024
        print(f"  Saved {filename} ({size:.1f} KB)")

    # Convert hotspots DataFrame to list of dicts
    hotspots_list = hotspots_df.to_dict(orient="records") if not hotspots_df.empty else []
    # Ensure serializable
    for h in hotspots_list:
        for k, v in h.items():
            if hasattr(v, "item"):
                h[k] = v.item()

    save_json(hotspots_list, "hotspots.json")
    save_json(temporal, "temporal.json")
    save_json(stations, "stations.json")
    save_json(heatmap, "heatmap.json")
    save_json(stats, "stats.json")
    save_json(vehicle_analysis, "vehicle_analysis.json")
    save_json(violation_analysis, "violation_analysis.json")

    # Also save the top violations for each hotspot as enforcement zones
    enforcement_zones = []
    for h in hotspots_list:
        enforcement_zones.append({
            "rank": h.get("enforcement_rank", h.get("rank", 0)),
            "cluster_id": h["cluster_id"],
            "lat": h["center_lat"],
            "lng": h["center_lng"],
            "location": h["top_location"],
            "police_station": h["police_station"],
            "violation_count": h["violation_count"],
            "congestion_score": h.get("congestion_impact_score", 0),
            "impact_level": h.get("impact_level", "Unknown"),
            "enforcement_priority": h.get("enforcement_priority", "Medium"),
            "enforcement_score": h.get("enforcement_priority_score", 0),
            "radius_m": h.get("radius_m", 200),
        })
    enforcement_zones.sort(key=lambda x: x.get("enforcement_score", 0), reverse=True)
    save_json(enforcement_zones, "enforcement_zones.json")

    print("\n" + "=" * 60)
    print("PRECOMPUTATION COMPLETE!")
    print(f"Output directory: {output_dir}")
    print(f"Total hotspots: {len(hotspots_list)}")
    print(f"Total violations processed: {len(df)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
