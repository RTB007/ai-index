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
  const stocks = data.stocks || {};

  // Display baskets: one line per basket instead of ~20 individual tickers. The broad "main"
  // basket from config.toml is split into three recognisable groups; power and gpu stay as they
  // are. Any configured ticker not listed here lands in "Other", so nothing silently vanishes
  // when config.toml changes.
  const SPLIT_MAIN = {
    "Chips": ["NVDA", "AMD", "AVGO", "TSM"],
    "Hyperscalers": ["MSFT", "GOOGL", "META"],
    "AI software": ["PLTR", "BOTZ"],
  };
  const groups = [];
  const placed = new Set();
  for (const [name, members] of Object.entries(SPLIT_MAIN)) {
    const m = members.filter(t => (baskets.main || []).includes(t));
    if (m.length) { groups.push({ name, members: m, color: null }); m.forEach(t => placed.add(t)); }
  }
  groups.push({ name: "Power", members: baskets.power || [] });
  groups.push({ name: "GPU cloud", members: baskets.gpu || [] });
  (baskets.power || []).concat(baskets.gpu || []).forEach(t => placed.add(t));
  const other = Object.values(baskets).flat().filter(t => !placed.has(t) && t !== benchmark);
  if (other.length) groups.push({ name: "Other", members: other });

  const COLORS = {
    "Chips": "#58a6ff", "Hyperscalers": "#a5d6ff", "AI software": "#f2cc60",
    "Power": "#3fb950", "GPU cloud": "#bc8cff", "Other": "#ff9bce",
  };

  // Equal-weight basket index, chain-linked on daily returns: on each trading day the basket
  // moves by the average return of the members that traded both that day and the previous one.
  // A member that lists later (e.g. CoreWeave) therefore joins without making the line jump,
  // which plain "rebase each ticker to 100 and average" would do.
  function basketIndex(members) {
    const byTicker = members
      .map(t => new Map((stocks[t] || []).map(p => [p.date, p.close])))
      .filter(m => m.size);
    if (!byTicker.length) return [];
    const dates = [...new Set(byTicker.flatMap(m => [...m.keys()]))].sort();
    const out = [{ x: dates[0], y: 100 }];
    let level = 100;
    for (let i = 1; i < dates.length; i++) {
      const rets = [];
      for (const m of byTicker) {
        const a = m.get(dates[i - 1]), b = m.get(dates[i]);
        if (a && b) rets.push(b / a - 1);
      }
      if (rets.length) level *= 1 + rets.reduce((s, r) => s + r, 0) / rets.length;
      out.push({ x: dates[i], y: level });
    }
    return out;
  }

  const stockDatasets = [];
  for (const g of groups) {
    const series = basketIndex(g.members);
    if (!series.length) continue;
    stockDatasets.push({
      label: g.name,
      members: g.members,
      data: series,
      borderColor: COLORS[g.name] || "#e6edf3",
      backgroundColor: "transparent",
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.15,
      yAxisID: "y2",
    });
  }
  if (benchmark && (stocks[benchmark] || []).length) {
    const s = stocks[benchmark];
    stockDatasets.push({
      label: "S&P 500 (" + benchmark + ")",
      data: s.map(p => ({ x: p.date, y: (p.close / s[0].close) * 100 })),
      borderColor: "#8b949e", backgroundColor: "transparent",
      borderWidth: 2, borderDash: [6, 4], pointRadius: 0, tension: 0.15, yAxisID: "y2",
    });
  }

  // Optional: the individual tickers, thin and hidden until asked for.
  const tickerDatasets = [];
  for (const g of groups) {
    for (const t of g.members) {
      const s = stocks[t] || [];
      if (!s.length) continue;
      tickerDatasets.push({
        label: t, isTicker: true, hidden: true,
        data: s.map(p => ({ x: p.date, y: (p.close / s[0].close) * 100 })),
        borderColor: (COLORS[g.name] || "#e6edf3") + "88", backgroundColor: "transparent",
        borderWidth: 1, pointRadius: 0, tension: 0.15, yAxisID: "y2",
      });
    }
  }

  // Basket members, listed under the chart.
  const legendEl = document.getElementById("basket-legend");
  if (legendEl) {
    legendEl.innerHTML = groups
      .filter(g => g.members.length)
      .map(g => `<span><i style="background:${COLORS[g.name] || "#e6edf3"}"></i><b>${g.name}</b> ${g.members.join(", ")}</span>`)
      .join("");
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

  const mainChart = new Chart(document.getElementById("main-chart"), {
    type: "line",
    data: { datasets: [scoreDataset, ...stockDatasets, ...tickerDatasets] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "nearest", axis: "x", intersect: false },
      plugins: {
        legend: { labels: {
          color: "#e6edf3", usePointStyle: true, boxWidth: 8, font: { size: 11 },
          // Individual tickers stay out of the legend; the checkbox below the chart shows them.
          filter: (item, chartData) => !chartData.datasets[item.datasetIndex].isTicker,
        } },
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
        // Logarithmic: GPU cloud went up ~6x and would flatten every other basket on a linear
        // axis. On a log axis a doubling is the same height everywhere, so baskets compare fairly.
        y2: { position: "right", type: "logarithmic",
              title: { display: true, text: "Baskets (equal-weight, = 100 at start, log scale)", color: "#8b949e" },
              grid: { drawOnChartArea: false },
              ticks: { color: "#8b949e",
                       callback: v => [50, 75, 100, 150, 200, 300, 400, 600, 800].includes(v) ? v : "" } },
      },
    },
  });

  const toggle = document.getElementById("show-tickers");
  if (toggle) {
    toggle.addEventListener("change", () => {
      mainChart.data.datasets.forEach(ds => { if (ds.isTicker) ds.hidden = !toggle.checked; });
      mainChart.update();
    });
  }

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
