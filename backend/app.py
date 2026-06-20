"""
app.py - Flask API server for ParkSense AI.
Serves precomputed analytics data to the frontend dashboard.
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

# Path to precomputed data
PRECOMPUTED_DIR = os.path.join(os.path.dirname(__file__), "precomputed")


def load_json(filename: str):
    """Load a precomputed JSON file."""
    filepath = os.path.join(PRECOMPUTED_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ---- API Endpoints ----


@app.route("/")
def index():
    """Root endpoint with API info."""
    return jsonify({
        "service": "ParkSense AI API",
        "status": "running",
        "endpoints": [
            "/api/stats",
            "/api/hotspots",
            "/api/heatmap",
            "/api/temporal",
            "/api/stations",
            "/api/enforcement-zones",
            "/api/vehicle-analysis",
            "/api/violation-analysis",
            "/api/health",
        ]
    })


@app.route("/api/stats")
def get_stats():
    """Dashboard summary statistics."""
    data = load_json("stats.json")
    if data is None:
        return jsonify({"error": "Stats not computed yet"}), 404
    return jsonify(data)


@app.route("/api/hotspots")
def get_hotspots():
    """All detected hotspot clusters."""
    data = load_json("hotspots.json")
    if data is None:
        return jsonify({"error": "Hotspots not computed yet"}), 404
    return jsonify(data)


@app.route("/api/heatmap")
def get_heatmap():
    """Heatmap data points [lat, lng, intensity]."""
    data = load_json("heatmap.json")
    if data is None:
        return jsonify({"error": "Heatmap not computed yet"}), 404
    return jsonify(data)


@app.route("/api/temporal")
def get_temporal():
    """Temporal analysis data."""
    data = load_json("temporal.json")
    if data is None:
        return jsonify({"error": "Temporal data not computed yet"}), 404
    return jsonify(data)


@app.route("/api/stations")
def get_stations():
    """Police station analytics."""
    data = load_json("stations.json")
    if data is None:
        return jsonify({"error": "Station data not computed yet"}), 404
    return jsonify(data)


@app.route("/api/enforcement-zones")
def get_enforcement_zones():
    """Prioritized enforcement zones."""
    data = load_json("enforcement_zones.json")
    if data is None:
        return jsonify({"error": "Enforcement zones not computed yet"}), 404
    return jsonify(data)


@app.route("/api/vehicle-analysis")
def get_vehicle_analysis():
    """Vehicle type breakdown analysis."""
    data = load_json("vehicle_analysis.json")
    if data is None:
        return jsonify({"error": "Vehicle analysis not computed yet"}), 404
    return jsonify(data)


@app.route("/api/violation-analysis")
def get_violation_analysis():
    """Violation type breakdown analysis."""
    data = load_json("violation_analysis.json")
    if data is None:
        return jsonify({"error": "Violation analysis not computed yet"}), 404
    return jsonify(data)


@app.route("/api/health")
def health_check():
    """Health check endpoint."""
    files = ["stats.json", "hotspots.json", "heatmap.json", "temporal.json",
             "stations.json", "enforcement_zones.json"]
    status = {}
    for f in files:
        status[f] = os.path.exists(os.path.join(PRECOMPUTED_DIR, f))
    return jsonify({"status": "ok", "data_files": status})


if __name__ == "__main__":
    print("Starting ParkSense AI API Server...")
    print(f"Precomputed data dir: {PRECOMPUTED_DIR}")
    app.run(debug=True, port=5000)
