/**
 * ParkSense AI — Dashboard Main Application
 * Fetches analytics data and renders interactive visualizations.
 */

// ============================================================
// CONFIG & STATE
// ============================================================
let API_BASE = import.meta.env.VITE_API_BASE || "/api";
if (API_BASE.startsWith("http") && !API_BASE.endsWith("/api") && !API_BASE.endsWith("/api/")) {
  API_BASE = API_BASE.endsWith("/") ? `${API_BASE}api` : `${API_BASE}/api`;
}
const BENGALURU_CENTER = [12.9716, 77.5946];
const TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>';

let appData = {};
let charts = {};
let maps = {};

// ============================================================
// INITIALIZATION
// ============================================================
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  setupNavigation();
  await loadAllData();
  hideLoading();
  renderOverview();
});

// ============================================================
// DATA LOADING
// ============================================================
async function fetchJSON(endpoint) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`Failed to fetch ${endpoint}:`, err);
    return null;
  }
}

async function loadAllData() {
  const [stats, hotspots, heatmap, temporal, stations, enforcement, vehicleAnalysis, violationAnalysis] =
    await Promise.all([
      fetchJSON("/stats"),
      fetchJSON("/hotspots"),
      fetchJSON("/heatmap"),
      fetchJSON("/temporal"),
      fetchJSON("/stations"),
      fetchJSON("/enforcement-zones"),
      fetchJSON("/vehicle-analysis"),
      fetchJSON("/violation-analysis"),
    ]);

  appData = { stats, hotspots, heatmap, temporal, stations, enforcement, vehicleAnalysis, violationAnalysis };
  console.log("All data loaded:", appData);
}

// ============================================================
// NAVIGATION
// ============================================================
const sectionTitles = {
  overview: "Overview Dashboard",
  heatmap: "Violation Heatmap",
  hotspots: "Hotspot Clusters",
  enforcement: "Enforcement Zones",
  temporal: "Temporal Analysis",
  stations: "Police Stations",
};

function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item");
  const menuToggle = document.getElementById("menu-toggle");
  const sidebar = document.getElementById("sidebar");

  navItems.forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const section = item.dataset.section;
      switchSection(section);
      if (window.innerWidth <= 768) sidebar.classList.remove("open");
    });
  });

  menuToggle.addEventListener("click", () => sidebar.classList.toggle("open"));
}

function switchSection(sectionId) {
  // Update nav
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
  document.querySelector(`[data-section="${sectionId}"]`).classList.add("active");

  // Update sections
  document.querySelectorAll(".section").forEach((s) => s.classList.remove("active"));
  document.getElementById(`section-${sectionId}`).classList.add("active");

  // Update title
  document.getElementById("page-title").textContent = sectionTitles[sectionId] || "Dashboard";

  // Lazy init sections
  if (sectionId === "heatmap" && !maps.heatmap) renderHeatmapSection();
  if (sectionId === "hotspots" && !maps.hotspots) renderHotspotsSection();
  if (sectionId === "enforcement" && !maps.enforcement) renderEnforcementSection();
  if (sectionId === "temporal" && !charts.hourly) renderTemporalSection();
  if (sectionId === "stations" && !maps.stations) renderStationsSection();

  // Invalidate map sizes after transition
  setTimeout(() => {
    Object.values(maps).forEach((m) => { if (m && m.invalidateSize) m.invalidateSize(); });
  }, 400);
}

// ============================================================
// LOADING SCREEN
// ============================================================
function hideLoading() {
  document.getElementById("loading-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
}

// ============================================================
// HELPERS
// ============================================================
function formatNumber(n) {
  if (n === undefined || n === null) return "—";
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return n.toLocaleString();
}

function impactColor(level) {
  const colors = { Critical: "#dc2626", High: "#f97316", Moderate: "#eab308", Low: "#22c55e" };
  return colors[level] || "#94a3b8";
}

function priorityColor(level) {
  const colors = { Urgent: "#dc2626", High: "#f97316", Medium: "#eab308", Low: "#22c55e" };
  return colors[level] || "#94a3b8";
}

function getGridColor() {
  const isLight = document.documentElement.classList.contains("light-theme");
  return isLight ? "rgba(15, 23, 42, 0.05)" : "rgba(255, 255, 255, 0.04)";
}

function createMap(containerId, zoom = 12) {
  const isLight = document.documentElement.classList.contains("light-theme");
  const tileUrl = isLight
    ? "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";

  const map = L.map(containerId, {
    zoomControl: true,
    attributionControl: false,
  }).setView(BENGALURU_CENTER, zoom);
  L.tileLayer(tileUrl, { attribution: TILE_ATTR, maxZoom: 18 }).addTo(map);
  return map;
}

// Theme management helpers
function initTheme() {
  const themeToggle = document.getElementById("theme-toggle");
  if (!themeToggle) return;

  themeToggle.addEventListener("click", () => {
    const isNowLight = document.documentElement.classList.toggle("light-theme");
    localStorage.setItem("theme", isNowLight ? "light" : "dark");
    
    // Update active maps
    updateMapThemes(isNowLight);
    
    // Update active charts
    updateChartThemes(isNowLight);
    
    // Re-render Hour x Day heatmap if data exists
    if (appData.temporal && appData.temporal.hour_day_heatmap) {
      renderHourDayHeatmap(appData.temporal.hour_day_heatmap);
    }
  });
}

function updateMapThemes(isLight) {
  const newUrl = isLight 
    ? "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
  
  Object.values(maps).forEach((map) => {
    if (map) {
      map.eachLayer((layer) => {
        if (layer instanceof L.TileLayer) {
          layer.setUrl(newUrl);
        }
      });
    }
  });
}

function updateChartThemes(isLight) {
  const textColor = isLight ? "#475569" : "#94a3b8";
  const gridColor = isLight ? "rgba(15, 23, 42, 0.05)" : "rgba(255, 255, 255, 0.04)";
  
  Chart.defaults.color = textColor;
  Chart.defaults.borderColor = isLight ? "rgba(15, 23, 42, 0.06)" : "rgba(255, 255, 255, 0.06)";

  Object.values(charts).forEach((chart) => {
    if (!chart) return;

    if (chart.options.scales) {
      Object.values(chart.options.scales).forEach((scale) => {
        if (scale.ticks) {
          scale.ticks.color = textColor;
        }
        if (scale.grid) {
          scale.grid.color = gridColor;
        }
        if (scale.angleLines) {
          scale.angleLines.color = gridColor;
        }
        if (scale.pointLabels) {
          scale.pointLabels.color = textColor;
        }
      });
    }

    if (chart.options.plugins && chart.options.plugins.legend) {
      if (!chart.options.plugins.legend.labels) {
        chart.options.plugins.legend.labels = {};
      }
      chart.options.plugins.legend.labels.color = textColor;
    }

    chart.update();
  });
}

// Chart.js default config
const isLightStartup = document.documentElement.classList.contains("light-theme");
Chart.defaults.color = isLightStartup ? "#475569" : "#94a3b8";
Chart.defaults.borderColor = isLightStartup ? "rgba(15, 23, 42, 0.06)" : "rgba(255, 255, 255, 0.06)";
Chart.defaults.font.family = "'Inter', sans-serif";

const chartColors = {
  orange: "rgba(245, 158, 11, 0.85)",
  orangeLight: "rgba(245, 158, 11, 0.15)",
  red: "rgba(239, 68, 68, 0.85)",
  redLight: "rgba(239, 68, 68, 0.15)",
  blue: "rgba(59, 130, 246, 0.85)",
  blueLight: "rgba(59, 130, 246, 0.15)",
  green: "rgba(34, 197, 94, 0.85)",
  greenLight: "rgba(34, 197, 94, 0.15)",
  purple: "rgba(139, 92, 246, 0.85)",
  purpleLight: "rgba(139, 92, 246, 0.15)",
  cyan: "rgba(6, 182, 212, 0.85)",
  amber: "rgba(251, 191, 36, 0.85)",
  pink: "rgba(236, 72, 153, 0.85)",
};

const doughnutColors = [
  chartColors.orange, chartColors.red, chartColors.blue,
  chartColors.green, chartColors.purple, chartColors.cyan,
  chartColors.amber, chartColors.pink,
];

// ============================================================
// OVERVIEW SECTION
// ============================================================
function renderOverview() {
  const s = appData.stats;
  if (!s) return;

  // KPI Cards
  document.getElementById("val-total-violations").textContent = formatNumber(s.total_violations);
  document.getElementById("val-hotspots").textContent = formatNumber(s.total_hotspots);
  document.getElementById("val-critical").textContent = formatNumber(s.critical_hotspots);
  document.getElementById("val-vehicles").textContent = formatNumber(s.unique_vehicles);
  document.getElementById("val-peak-hour").textContent = s.peak_hour_label || "—";
  document.getElementById("val-avg-score").textContent = s.avg_congestion_score || "—";

  // Date range
  if (s.date_range) {
    document.querySelector("#date-range span").textContent =
      `${s.date_range.start} — ${s.date_range.end}`;
  }

  // Violation Types Chart
  if (s.top_violations) {
    const labels = Object.keys(s.top_violations).map((l) => l.length > 20 ? l.slice(0, 18) + "…" : l);
    const data = Object.values(s.top_violations);
    charts.violationTypes = new Chart(document.getElementById("chart-violation-types"), {
      type: "doughnut",
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: doughnutColors,
          borderColor: "transparent",
          borderWidth: 0,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { position: "right", labels: { boxWidth: 12, padding: 12, font: { size: 11 } } },
        },
      },
    });
  }

  // Vehicle Types Chart
  if (s.vehicle_distribution) {
    const labels = Object.keys(s.vehicle_distribution);
    const data = Object.values(s.vehicle_distribution);
    charts.vehicleTypes = new Chart(document.getElementById("chart-vehicle-types"), {
      type: "doughnut",
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: [chartColors.blue, chartColors.orange, chartColors.green, chartColors.purple, chartColors.cyan],
          borderColor: "transparent",
          borderWidth: 0,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { position: "right", labels: { boxWidth: 12, padding: 12, font: { size: 11 } } },
        },
      },
    });
  }

  // Overview mini map
  renderOverviewMap();

  // Top zones table
  renderTopZonesTable();
}

function renderOverviewMap() {
  if (!appData.heatmap) return;
  maps.overview = createMap("overview-map", 11);
  const heat = L.heatLayer(appData.heatmap, {
    radius: 18,
    blur: 22,
    maxZoom: 15,
    gradient: { 0.2: "#22c55e", 0.4: "#eab308", 0.6: "#f97316", 0.8: "#ef4444", 1.0: "#dc2626" },
  });
  heat.addTo(maps.overview);
}

function renderTopZonesTable() {
  const zones = appData.enforcement;
  if (!zones || zones.length === 0) return;

  const top10 = zones.slice(0, 10);
  let html = `<table class="data-table">
    <thead><tr>
      <th>Rank</th><th>Location</th><th>Station</th><th>Violations</th><th>Impact</th><th>Priority</th>
    </tr></thead><tbody>`;

  top10.forEach((z, i) => {
    const rankClass = i < 3 ? "top" : "normal";
    const location = (z.location || "Unknown").slice(0, 40);
    html += `<tr>
      <td><span class="rank-num ${rankClass}">${i + 1}</span></td>
      <td>${location}</td>
      <td>${z.police_station || "—"}</td>
      <td style="font-family:var(--font-mono);font-weight:600;">${formatNumber(z.violation_count)}</td>
      <td><span class="badge ${(z.impact_level || "").toLowerCase()}">${z.impact_level || "—"}</span></td>
      <td><span class="badge ${(z.enforcement_priority || "").toLowerCase()}">${z.enforcement_priority || "—"}</span></td>
    </tr>`;
  });

  html += "</tbody></table>";
  document.getElementById("top-zones-table").innerHTML = html;
}

// ============================================================
// HEATMAP SECTION
// ============================================================
function renderHeatmapSection() {
  if (!appData.heatmap) return;
  maps.heatmap = createMap("heatmap", 12);
  const heat = L.heatLayer(appData.heatmap, {
    radius: 20,
    blur: 25,
    maxZoom: 16,
    max: 15,
    gradient: { 0.15: "#22c55e", 0.35: "#eab308", 0.55: "#f97316", 0.75: "#ef4444", 1.0: "#dc2626" },
  });
  heat.addTo(maps.heatmap);
}

// ============================================================
// HOTSPOTS SECTION
// ============================================================
function renderHotspotsSection() {
  if (!appData.hotspots) return;
  maps.hotspots = createMap("hotspots-map", 12);

  appData.hotspots.forEach((h) => {
    const color = impactColor(h.impact_level);
    const size = Math.max(24, Math.min(50, 20 + h.violation_count / 50));

    const icon = L.divIcon({
      className: "hotspot-marker",
      html: `<div style="width:${size}px;height:${size}px;background:${color};border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:0.6rem;font-weight:700;color:white;font-family:var(--font-mono);border:2px solid rgba(255,255,255,0.3);box-shadow:0 2px 12px ${color}60;">${h.rank || ""}</div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });

    const marker = L.marker([h.center_lat, h.center_lng], { icon }).addTo(maps.hotspots);

    // Build popup
    const violationBreakdown = h.violation_breakdown
      ? Object.entries(h.violation_breakdown).map(([k, v]) => `${k}: ${v}`).join("<br>")
      : "N/A";

    marker.bindPopup(`
      <div style="min-width:220px;">
        <strong>Hotspot #${h.rank || h.cluster_id}</strong><br>
        <span style="color:${color};font-weight:600;">${h.impact_level}</span> — Score: ${h.congestion_impact_score || 0}<br><br>
        📍 ${(h.top_location || "").slice(0, 60)}<br>
        🏛️ ${h.police_station || "—"}<br>
        🚗 Violations: <strong>${h.violation_count}</strong><br>
        🚘 Unique vehicles: ${h.unique_vehicles}<br>
        📐 Radius: ${Math.round(h.radius_m || 0)}m<br><br>
        <strong>Violations:</strong><br>${violationBreakdown}
      </div>
    `);

    // Radius circle
    L.circle([h.center_lat, h.center_lng], {
      radius: h.radius_m || 200,
      color: color,
      fillColor: color,
      fillOpacity: 0.08,
      weight: 1.5,
      opacity: 0.4,
    }).addTo(maps.hotspots);
  });

  // Charts
  renderHotspotCharts();
}

function renderHotspotCharts() {
  const hotspots = appData.hotspots;
  if (!hotspots || hotspots.length === 0) return;

  // Impact distribution pie
  const impactCounts = { Critical: 0, High: 0, Moderate: 0, Low: 0 };
  hotspots.forEach((h) => { if (impactCounts[h.impact_level] !== undefined) impactCounts[h.impact_level]++; });

  charts.hotspotImpact = new Chart(document.getElementById("chart-hotspot-impact"), {
    type: "doughnut",
    data: {
      labels: Object.keys(impactCounts),
      datasets: [{
        data: Object.values(impactCounts),
        backgroundColor: ["#dc2626", "#f97316", "#eab308", "#22c55e"],
        borderColor: "transparent",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "60%",
      plugins: { legend: { position: "right", labels: { boxWidth: 12, padding: 12 } } },
    },
  });

  // Top 15 hotspot scores bar
  const top15 = hotspots.slice(0, 15);
  charts.hotspotScores = new Chart(document.getElementById("chart-hotspot-scores"), {
    type: "bar",
    data: {
      labels: top15.map((h) => `#${h.rank || h.cluster_id}`),
      datasets: [{
        label: "Congestion Score",
        data: top15.map((h) => h.congestion_impact_score || 0),
        backgroundColor: top15.map((h) => impactColor(h.impact_level) + "cc"),
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      scales: {
        x: { grid: { color: getGridColor() }, max: 100 },
        y: { grid: { display: false } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

// ============================================================
// ENFORCEMENT SECTION
// ============================================================
function renderEnforcementSection() {
  if (!appData.enforcement) return;
  maps.enforcement = createMap("enforcement-map", 12);

  appData.enforcement.forEach((z, i) => {
    const color = priorityColor(z.enforcement_priority);
    const size = Math.max(26, Math.min(50, 22 + z.violation_count / 40));

    const icon = L.divIcon({
      className: "hotspot-marker",
      html: `<div style="width:${size}px;height:${size}px;background:${color};border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:0.65rem;font-weight:700;color:white;font-family:var(--font-mono);border:2px solid rgba(255,255,255,0.3);box-shadow:0 2px 12px ${color}60;">${i + 1}</div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });

    const marker = L.marker([z.lat, z.lng], { icon }).addTo(maps.enforcement);

    marker.bindPopup(`
      <div style="min-width:200px;">
        <strong>Zone #${i + 1}</strong> — <span style="color:${color};font-weight:700;">${z.enforcement_priority}</span><br><br>
        📍 ${(z.location || "").slice(0, 50)}<br>
        🏛️ ${z.police_station || "—"}<br>
        🚗 Violations: <strong>${z.violation_count}</strong><br>
        📊 Congestion Score: ${z.congestion_score}<br>
        🎯 Enforcement Score: ${z.enforcement_score}<br>
        📐 Radius: ${Math.round(z.radius_m || 0)}m
      </div>
    `);

    L.circle([z.lat, z.lng], {
      radius: z.radius_m || 200,
      color: color,
      fillColor: color,
      fillOpacity: 0.1,
      weight: 2,
      opacity: 0.5,
      dashArray: z.enforcement_priority === "Urgent" ? null : "5, 8",
    }).addTo(maps.enforcement);
  });

  // Enforcement table
  renderEnforcementTable();
}

function renderEnforcementTable() {
  const zones = appData.enforcement;
  if (!zones) return;

  let html = `<table class="data-table">
    <thead><tr>
      <th>Rank</th><th>Location</th><th>Police Station</th><th>Violations</th>
      <th>Congestion Score</th><th>Enforcement Score</th><th>Impact</th><th>Priority</th>
    </tr></thead><tbody>`;

  zones.forEach((z, i) => {
    const rankClass = i < 3 ? "top" : "normal";
    html += `<tr>
      <td><span class="rank-num ${rankClass}">${i + 1}</span></td>
      <td>${(z.location || "Unknown").slice(0, 45)}</td>
      <td>${z.police_station || "—"}</td>
      <td style="font-family:var(--font-mono);font-weight:600;">${formatNumber(z.violation_count)}</td>
      <td style="font-family:var(--font-mono);font-weight:600;color:${impactColor(z.impact_level)};">${z.congestion_score}</td>
      <td style="font-family:var(--font-mono);font-weight:600;color:${priorityColor(z.enforcement_priority)};">${z.enforcement_score}</td>
      <td><span class="badge ${(z.impact_level || "").toLowerCase()}">${z.impact_level}</span></td>
      <td><span class="badge ${(z.enforcement_priority || "").toLowerCase()}">${z.enforcement_priority}</span></td>
    </tr>`;
  });

  html += "</tbody></table>";
  document.getElementById("enforcement-table").innerHTML = html;
}

// ============================================================
// TEMPORAL SECTION
// ============================================================
function renderTemporalSection() {
  const t = appData.temporal;
  if (!t) return;

  // Hourly chart
  if (t.hourly) {
    charts.hourly = new Chart(document.getElementById("chart-hourly"), {
      type: "bar",
      data: {
        labels: t.hourly.map((d) => `${String(d.hour).padStart(2, "0")}:00`),
        datasets: [{
          label: "Violations",
          data: t.hourly.map((d) => d.count),
          backgroundColor: t.hourly.map((d) =>
            (d.hour >= 7 && d.hour <= 10) || (d.hour >= 17 && d.hour <= 20)
              ? chartColors.red : chartColors.orange
          ),
          borderRadius: 4,
          borderSkipped: false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { grid: { color: getGridColor() }, beginAtZero: true },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterLabel: (ctx) => {
                const hr = t.hourly[ctx.dataIndex].hour;
                return (hr >= 7 && hr <= 10) || (hr >= 17 && hr <= 20) ? "⚠️ Peak Hour" : "";
              }
            }
          }
        },
      },
    });
  }

  // Daily chart
  if (t.daily) {
    charts.daily = new Chart(document.getElementById("chart-daily"), {
      type: "bar",
      data: {
        labels: t.daily.map((d) => d.day_name),
        datasets: [{
          label: "Violations",
          data: t.daily.map((d) => d.count),
          backgroundColor: chartColors.blue,
          borderRadius: 6,
          borderSkipped: false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { grid: { color: getGridColor() }, beginAtZero: true },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // Monthly chart
  if (t.monthly) {
    charts.monthly = new Chart(document.getElementById("chart-monthly"), {
      type: "line",
      data: {
        labels: t.monthly.map((d) => d.month_name),
        datasets: [{
          label: "Violations",
          data: t.monthly.map((d) => d.count),
          borderColor: chartColors.orange,
          backgroundColor: chartColors.orangeLight,
          fill: true,
          tension: 0.4,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointBackgroundColor: chartColors.orange,
          borderWidth: 2.5,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { grid: { color: getGridColor() }, beginAtZero: true },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // Time buckets chart
  if (t.time_buckets) {
    const bucketColors = [chartColors.amber, chartColors.green, chartColors.red, chartColors.purple];
    charts.timeBuckets = new Chart(document.getElementById("chart-time-buckets"), {
      type: "polarArea",
      data: {
        labels: t.time_buckets.map((d) => d.time_bucket),
        datasets: [{
          data: t.time_buckets.map((d) => d.count),
          backgroundColor: bucketColors.map((c) => c.replace("0.85", "0.5")),
          borderColor: bucketColors,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "right", labels: { boxWidth: 12, padding: 12 } } },
        scales: { r: { grid: { color: getGridColor() }, ticks: { display: false } } },
      },
    });
  }

  // Hour × Day heatmap grid
  if (t.hour_day_heatmap) renderHourDayHeatmap(t.hour_day_heatmap);
}

function renderHourDayHeatmap(data) {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const maxCount = Math.max(...data.map((d) => d.count));
  const isLight = document.documentElement.classList.contains("light-theme");

  let html = '<div class="heatmap-grid">';

  // Header row
  html += '<div class="heatmap-label"></div>';
  for (let h = 0; h < 24; h++) {
    html += `<div class="heatmap-header">${String(h).padStart(2, "0")}</div>`;
  }

  // Data rows
  for (let d = 0; d < 7; d++) {
    html += `<div class="heatmap-label">${days[d]}</div>`;
    for (let h = 0; h < 24; h++) {
      const entry = data.find((e) => e.day_of_week === d && e.hour === h);
      const count = entry ? entry.count : 0;
      const intensity = maxCount > 0 ? count / maxCount : 0;
      const bg = heatmapColor(intensity, isLight);
      const textStyle = count > 0 ? "color: white;" : "";
      html += `<div class="heatmap-cell" style="background:${bg};${textStyle}" title="${days[d]} ${h}:00 — ${count} violations">${count > 0 ? count : ""}</div>`;
    }
  }

  html += "</div>";
  document.getElementById("hour-day-heatmap").innerHTML = html;
}

function heatmapColor(intensity, isLight) {
  if (intensity === 0) return isLight ? "rgba(15, 23, 42, 0.04)" : "rgba(255, 255, 255, 0.03)";
  if (intensity < 0.25) return `rgba(34, 197, 94, ${0.2 + intensity * 1.5})`;
  if (intensity < 0.5) return `rgba(234, 179, 8, ${0.3 + intensity})`;
  if (intensity < 0.75) return `rgba(249, 115, 22, ${0.4 + intensity * 0.6})`;
  return `rgba(220, 38, 38, ${0.5 + intensity * 0.5})`;
}

// ============================================================
// STATIONS SECTION
// ============================================================
function renderStationsSection() {
  if (!appData.stations) return;
  maps.stations = createMap("stations-map", 11);

  const maxViolations = Math.max(...appData.stations.map((s) => s.total_violations));

  appData.stations.forEach((s) => {
    const size = Math.max(22, Math.min(45, 18 + (s.total_violations / maxViolations) * 30));

    const icon = L.divIcon({
      className: "station-marker",
      html: `<div style="width:${size}px;height:${size}px;" class="station-marker">${formatNumber(s.total_violations)}</div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });

    const marker = L.marker([s.center_lat, s.center_lng], { icon }).addTo(maps.stations);

    marker.bindPopup(`
      <div style="min-width:200px;">
        <strong>🏛️ ${s.station}</strong><br><br>
        🚗 Total Violations: <strong>${formatNumber(s.total_violations)}</strong><br>
        🚘 Unique Vehicles: ${formatNumber(s.unique_vehicles)}<br>
        ⚡ Avg Severity: ${s.avg_severity}<br>
        ⏰ Peak Hour %: ${s.peak_hour_pct}%<br>
        🔄 Action Rate: ${s.action_rate}%<br>
        ✅ Validated: ${s.validated_pct}%<br>
        🚨 Top Violation: ${s.top_violation}<br>
        🚙 Top Vehicle: ${s.top_vehicle}
      </div>
    `);
  });

  // Station bar chart
  const top20 = appData.stations.slice(0, 20);
  charts.stations = new Chart(document.getElementById("chart-stations"), {
    type: "bar",
    data: {
      labels: top20.map((s) => s.station),
      datasets: [{
        label: "Total Violations",
        data: top20.map((s) => s.total_violations),
        backgroundColor: chartColors.blue,
        borderRadius: 5,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      scales: {
        x: { grid: { color: getGridColor() }, beginAtZero: true },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } },
      },
      plugins: { legend: { display: false } },
    },
  });
}
