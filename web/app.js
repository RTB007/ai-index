(async () => {
  const res = await fetch("data.json?t=" + Date.now());
  if (!res.ok) {
    document.getElementById("latest-rationale").textContent = "Failed to load data.json";
    return;
  }
  const data = await res.json();

  // ---- Latest score card ----
  const scores = data.scores || [];
  const latest = scores[scores.length - 1];
  if (latest) {
    document.getElementById("latest-score").textContent = latest.score;
    document.getElementById("latest-date").textContent = latest.date;
    document.getElementById("latest-rationale").textContent =
      latest.rationale || "(no rationale recorded)";
    // Color the big number per band.
    const el = document.getElementById("latest-score");
    const s = latest.score;
    el.style.color =
      s >= 80 ? "var(--hot)" :
      s >= 60 ? "var(--accent)" :
      s >= 40 ? "var(--warn)" :
      "var(--good)";
  } else {
    document.getElementById("latest-rationale").textContent =
      "No scores yet. Run scripts/daily.py to generate one.";
  }

  document.getElementById("generated").textContent =
    "generated " + (data.generated_at || "?");

  // ---- Main chart: fantasy score (left y) + normalized stocks (right y) ----
  const stockDatasets = [];
  const stockPalette = ["#58a6ff","#a371f7","#7ee787","#f0883e","#ff7b72","#d2a8ff","#79c0ff","#ffa657","#56d364"];
  let colorIdx = 0;
  for (const ticker of (data.tickers || [])) {
    const series = (data.stocks || {})[ticker] || [];
    if (!series.length) continue;
    const base = series[0].close;
    stockDatasets.push({
      label: ticker,
      data: series.map(p => ({ x: p.date, y: (p.close / base) * 100 })),
      borderColor: stockPalette[colorIdx % stockPalette.length],
      backgroundColor: "transparent",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.15,
      yAxisID: "y2",
    });
    colorIdx++;
  }

  const scoreDataset = {
    label: "AI Fantasy Index",
    data: scores.map(s => ({ x: s.date, y: s.score, rationale: s.rationale })),
    borderColor: "#ff7a45",
    backgroundColor: "rgba(255,122,69,0.12)",
    borderWidth: 3,
    pointRadius: 0,
    pointHoverRadius: 5,
    tension: 0.2,
    fill: true,
    yAxisID: "y1",
  };

  new Chart(document.getElementById("main-chart"), {
    type: "line",
    data: { datasets: [scoreDataset, ...stockDatasets] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "nearest", axis: "x", intersect: false },
      plugins: {
        legend: { labels: { color: "#e6edf3", usePointStyle: true, boxWidth: 8 } },
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const it = items.find(i => i.dataset.label === "AI Fantasy Index");
              return it?.raw?.rationale ? "\n" + it.raw.rationale : "";
            },
          },
        },
      },
      scales: {
        x: {
          type: "time",
          time: { unit: "month" },
          grid: { color: "#232a35" },
          ticks: { color: "#8b949e" },
        },
        y1: {
          position: "left",
          min: 0, max: 100,
          title: { display: true, text: "Fantasy index (0-100)", color: "#8b949e" },
          grid: { color: "#232a35" },
          ticks: { color: "#8b949e" },
        },
        y2: {
          position: "right",
          title: { display: true, text: "Stocks (rebased = 100)", color: "#8b949e" },
          grid: { drawOnChartArea: false },
          ticks: { color: "#8b949e" },
        },
      },
    },
  });

  // ---- Components chart: latest sub-scores ----
  if (latest && latest.components) {
    const keys = Object.keys(latest.components);
    new Chart(document.getElementById("components-chart"), {
      type: "bar",
      data: {
        labels: keys,
        datasets: [{
          label: "sub-score",
          data: keys.map(k => latest.components[k]),
          backgroundColor: "#ff7a45",
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: "#232a35" }, ticks: { color: "#8b949e" } },
          y: { min: 0, max: 100, grid: { color: "#232a35" }, ticks: { color: "#8b949e" } },
        },
      },
    });
  }
})();
