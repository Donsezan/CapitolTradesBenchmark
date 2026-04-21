const CHART_COLORS = [
  '#7c6af7', '#34d399', '#f59e0b', '#60a5fa', '#f472b6',
  '#a78bfa', '#2dd4bf', '#fb923c',
];

let compChart = null;
let allocChart = null;

function initComparisonChart() {
  const ctx = document.getElementById('comparisonChart').getContext('2d');
  compChart = new Chart(ctx, {
    type: 'line',
    data: { datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y >= 0 ? '+' : ''}${ctx.parsed.y.toFixed(2)}%`,
          },
        },
      },
      scales: {
        x: {
          type: 'category',
          ticks: { color: '#475569', maxTicksLimit: 8, font: { size: 10 } },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        y: {
          ticks: {
            color: '#475569',
            font: { size: 10 },
            callback: v => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`,
          },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
      },
    },
  });
}

function updateComparisonChart(benchmarkData, politicianData) {
  if (!compChart) initComparisonChart();

  const benchSeries = benchmarkData.series || [];

  // Use union of all series dates so politician lines aren't clipped by benchmark gaps
  const dateSet = new Set(benchSeries.map(p => p.date));
  politicianData.forEach(pol => (pol.series || []).forEach(p => dateSet.add(p.date)));
  const labels = [...dateSet].sort();

  const benchLookup = {};
  benchSeries.forEach(p => { benchLookup[p.date] = p.value; });

  const datasets = [
    {
      label: `Benchmark (${benchmarkData.ticker}) ${benchmarkData.return_pct >= 0 ? '+' : ''}${benchmarkData.return_pct?.toFixed(1) ?? '?'}%`,
      data: labels.map(d => benchLookup[d] ?? null),
      borderColor: '#94a3b8',
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      spanGaps: true,
    },
    ...politicianData.map((pol, i) => {
      const lookup = {};
      (pol.series || []).forEach(p => { lookup[p.date] = p.value; });
      return {
        label: `${pol.name} (${pol.party}) ${pol.return_pct >= 0 ? '+' : ''}${pol.return_pct?.toFixed(1) ?? '?'}%`,
        data: labels.map(d => lookup[d] ?? null),
        borderColor: pol.color || CHART_COLORS[i % CHART_COLORS.length],
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.3,
        spanGaps: true,
      };
    }),
  ];

  compChart.data.labels = labels;
  compChart.data.datasets = datasets;
  compChart.update();
}

function renderAllocationChart(holdings) {
  const ctx = document.getElementById('allocationChart').getContext('2d');
  if (allocChart) { allocChart.destroy(); allocChart = null; }
  if (!holdings.length) return;

  allocChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: holdings.map(h => h.ticker),
      datasets: [{
        data: holdings.map(h => h.shares * h.current_price),
        backgroundColor: CHART_COLORS.slice(0, holdings.length),
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: { labels: { color: '#94a3b8', boxWidth: 10, font: { size: 10 } } },
      },
    },
  });
}
