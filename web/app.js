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

  // ---- Group tickers by basket for visual distinction ----
  const baskets = data.baskets || { main: data.tickers || [], power: [], gpu: [] };
  const benchmark = data.benchmark;

  // Per-basket color schemes — use hue families so each basket is recognizable.
  const palette = {
    main:      ["#58a6ff", "#79c0ff", "#a5d6ff", "#bee5fb", "#cce7ff", "#1f6feb", "#388bfd", "#6cb6ff", "#54aeff"],
    power:    ["#7ee787", "#5dde66", "#3fb950", "#2da44e", "#26913c"],
    gpu:      ["#d2a8ff", "#bc8cff", "#a371f7", "#8957e5", "#6e40c9"],
    benchmark: "#8b949e", // grey dashed
  };

  const stockDatasets = [];
  function pushBasket(name, tickerList, isBench=false) {
    let idx = 0;
    for (const ticker of tickerList) {
      const series = (data.stocks || {})[ticker] || [];
      if (!series.length) continue;
      const base = series[0].close;
      stockDatasets.push({
        label: ticker + (name === "main" ? "" : " (" + name + ")"),
        data: series.map(p => ({ x: p.date, y: (p.close / base) * 100 })),
        borderColor: isBench ? palette.benchmark : palette[name][idx % palette[name].length],
        backgroundColor: "transparent",
        borderWidth: isBench ? 2 : 1.3,
        borderDash: isBench ? [6, 4] : [],
        pointRadius: 0,
        tension: 0.15,
        yAxisID: "y2",
      });
      idx++;
    }
  }
  pushBasket("main", baskets.main || []);
  pushBasket("power", baskets.power || []);
  pushBasket("gpu", baskets.gpu || []);
  if (benchmark) pushBasket("bench", [benchmark], true);

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
        legend: { labels: { color: "#e6edf3", usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
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
        x: { type: "time", time: { unit: "month" },
             grid: { color: "#232a35" }, ticks: { color: "#8b949e" } },
        y1: { position: "left", min: 0, max: 100,
              title: { display: true, text: "Fantasy index (0-100)", color: "#8b949e" },
              grid: { color: "#232a35" }, ticks: { color: "#8b949e" } },
        y2: { position: "right",
              title: { display: true, text: "Stocks (rebased = 100)", color: "#8b949e" },
              grid: { drawOnChartArea: false }, ticks: { color: "#8b949e" } },
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
