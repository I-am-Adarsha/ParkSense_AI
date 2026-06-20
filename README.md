# 🅿️ ParkSense AI — Intelligent Parking Violation Analytics

> **AI-driven parking intelligence for detecting illegal parking hotspots and quantifying their impact on traffic flow in Bengaluru.**

Built for **Flipkart Gridlock Hackathon 2.0 — Round 2 (Prototype Phase)**

---

## 🎯 Problem Statement

**Poor Visibility on Parking-Induced Congestion**

On-street illegal parking and spillover parking near commercial areas, metro stations, and events choke carriageways and intersections. Enforcement is patrol-based and reactive, with no heatmap of violations vs. congestion impact, making it difficult to prioritize enforcement zones.

## 💡 Solution

ParkSense AI uses **machine learning and geospatial analytics** to transform raw violation data into actionable intelligence:

1. **Hotspot Detection** — DBSCAN spatial clustering identifies geographical clusters of illegal parking
2. **Congestion Impact Scoring** — Multi-factor weighted model quantifies how each hotspot impacts traffic flow
3. **Temporal Pattern Analysis** — Time-series decomposition reveals peak violation periods
4. **Enforcement Prioritization** — Composite ranking algorithm enables targeted, data-driven enforcement

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **Backend** | Python, Flask, pandas, scikit-learn, HDBSCAN |
| **Frontend** | Vite, Vanilla JS, Leaflet.js, Chart.js |
| **ML Models** | DBSCAN clustering, weighted scoring models |
| **Data** | 298,000+ parking violation records from Bengaluru |

## 📊 Features

- **Interactive Heatmap** — Violation density visualization across Bengaluru
- **Hotspot Clusters** — AI-detected parking violation clusters with impact scores
- **Enforcement Priority Board** — Ranked zones for targeted enforcement
- **Temporal Analysis** — Hourly, daily, monthly violation patterns
- **Police Station Analytics** — Per-station violation breakdown
- **Hour×Day Heatmap** — Granular temporal pattern visualization

---

## 🚀 Instructions to Run

### Prerequisites
- **Python 3.10+** with pip
- **Node.js 18+** with npm

### Step 1: Clone and Setup

```bash
cd Flipkart_Gridlock
```

### Step 2: Install Backend Dependencies

```bash
pip install -r backend/requirements.txt
```

### Step 3: Run Data Processing (one-time)

> This processes the 298K+ violation records and generates precomputed analytics.

```bash
python backend/precompute.py
```

Wait for the script to complete (~2-3 minutes).

### Step 4: Start the Backend API Server

```bash
python backend/app.py
```

The Flask API server will start on `http://localhost:5000`.

### Step 5: Install Frontend Dependencies

```bash
cd frontend
npm install
```

### Step 6: Start the Frontend Dashboard

```bash
npm run dev
```

The dashboard will open at `http://localhost:3000`.

---

## 📁 Project Structure

```
Flipkart_Gridlock/
├── backend/
│   ├── app.py                # Flask API server
│   ├── data_processor.py     # Data loading, cleaning, feature engineering
│   ├── models.py             # ML models (DBSCAN, scoring, temporal analysis)
│   ├── precompute.py         # Pre-computation pipeline
│   ├── requirements.txt      # Python dependencies
│   └── precomputed/          # Generated JSON analytics data
│       ├── stats.json
│       ├── hotspots.json
│       ├── heatmap.json
│       ├── temporal.json
│       ├── stations.json
│       ├── enforcement_zones.json
│       ├── vehicle_analysis.json
│       └── violation_analysis.json
├── frontend/
│   ├── index.html            # Dashboard HTML
│   ├── style.css             # Premium dark-mode CSS
│   ├── main.js               # Dashboard logic & visualizations
│   ├── package.json          # Frontend dependencies
│   └── vite.config.js        # Vite configuration
├── jan to may police violation_anonymized791b166.csv  # Dataset
└── README.md
```

## 👥 Team

**ATAdarsha's Team** — Flipkart Gridlock Hackathon 2.0

## 📜 License

This project was built for the Flipkart Gridlock Hackathon 2.0.
