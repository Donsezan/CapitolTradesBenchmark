/* ── State ──────────────────────────────────────────── */
let currentRange = '1Y';
let currentBenchmark = '^GSPC';
let currentPartyFilter = '';
// id → { id, name, party, color }
const selectedPoliticians = new Map();
let allPoliticians = [];
let _compReqId = 0;

/* ── Bootstrap ─────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  initComparisonChart();
  await Promise.all([
    loadAllPoliticians(),
    loadTradeFeed(),
    loadSubscriptions(),
    loadLeaderboard(),
  ]);
  populatePoliticianSelects();
  wireControls();
});

/* ── Controls ───────────────────────────────────────── */
function wireControls() {
  document.getElementById('rangePills').addEventListener('click', e => {
    const btn = e.target.closest('.pill');
    if (!btn) return;
    document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    currentRange = btn.dataset.range;
    refreshComparison();
  });

  const benchSelect = document.getElementById('benchmarkSelect');
  const benchCustom = document.getElementById('benchmarkCustom');

  benchSelect.addEventListener('change', () => {
    if (benchSelect.value === 'custom') {
      benchCustom.style.display = 'inline-block';
      benchCustom.focus();
    } else {
      benchCustom.style.display = 'none';
      currentBenchmark = benchSelect.value;
      refreshComparison();
    }
  });

  benchCustom.addEventListener('change', () => {
    if (benchCustom.value.trim()) {
      currentBenchmark = benchCustom.value.trim().toUpperCase();
      refreshComparison();
    }
  });

  wirePartyFilter();
  // custom politician search dropdown
  wireSearchDropdown();

  document.getElementById('closeDetail').addEventListener('click', () => {
    document.getElementById('politicianDetail').style.display = 'none';
  });

  document.getElementById('toggleDetail').addEventListener('click', () => {
    const body = document.getElementById('detailBody');
    const btn = document.getElementById('toggleDetail');
    const collapsed = body.style.display === 'none';
    body.style.display = collapsed ? '' : 'none';
    btn.innerHTML = collapsed ? '&#x2212;' : '&#x2b;';
    btn.title = collapsed ? 'Minimize' : 'Expand';
  });

  document.getElementById('refreshPricesBtn').addEventListener('click', async () => {
    const btn = document.getElementById('refreshPricesBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Updating…';
    try {
      await API.updatePrices();
      btn.textContent = '✓ Done';
      setTimeout(() => {
        btn.textContent = '↻ Refresh Prices';
        btn.disabled = false;
      }, 2000);
      await loadAllPoliticians();
      refreshComparison();
    } catch (err) {
      btn.textContent = '✗ Error';
      setTimeout(() => {
        btn.textContent = '↻ Refresh Prices';
        btn.disabled = false;
      }, 2000);
    }
  });

  document.getElementById('enrichPartiesBtn').addEventListener('click', async () => {
    const btn = document.getElementById('enrichPartiesBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Enriching…';
    try {
      const data = await API.enrichParties();
      btn.textContent = `✓ Updated ${data.updated}/${data.total}`;
      if (data.updated > 0) await loadAllPoliticians();
    } catch (err) {
      btn.textContent = '✗ Error';
    }
    setTimeout(() => {
      btn.textContent = '★ Enrich Parties';
      btn.disabled = false;
    }, 3000);
  });

  document.getElementById('subscribBtn').addEventListener('click', handleSubscribe);

  document.getElementById('toggleTradeFeed').addEventListener('click', () => {
    const body = document.getElementById('tradeFeedBody');
    const btn = document.getElementById('toggleTradeFeed');
    const collapsed = body.style.display === 'none';
    body.style.display = collapsed ? '' : 'none';
    btn.innerHTML = collapsed ? '&#x2212;' : '&#x2b;';
    btn.title = collapsed ? 'Minimize' : 'Expand';
  });

  document.getElementById('toggleLeaderboard').addEventListener('click', () => {
    const body = document.getElementById('leaderboardBody');
    const btn = document.getElementById('toggleLeaderboard');
    const collapsed = body.style.display === 'none';
    body.style.display = collapsed ? '' : 'none';
    btn.innerHTML = collapsed ? '&#x2212;' : '&#x2b;';
    btn.title = collapsed ? 'Minimize' : 'Expand';
  });

  document.getElementById('leaderboardSort').addEventListener('change', () => {
    loadLeaderboard();
  });
}

/* ── Politicians search dropdown ───────────────────── */
async function loadAllPoliticians() {
  try {
    const data = await API.politicians();
    allPoliticians = data;
    renderDropdownOptions('');
  } catch (err) {
    console.warn('Could not load politicians:', err.message);
  }
}

function renderDropdownOptions(query) {
  const dropdown = document.getElementById('polDropdown');
  const q = query.toLowerCase().trim();
  const filtered = allPoliticians.filter(p => {
    if (currentPartyFilter && p.party !== currentPartyFilter) return false;
    return !q || p.name.toLowerCase().includes(q);
  });

  if (!filtered.length) {
    dropdown.innerHTML = `<div class="pol-dropdown-empty">No politicians found</div>`;
    return;
  }

  dropdown.innerHTML = filtered.map(p => {
    const id = p.politician_id ?? p.id;
    const added = selectedPoliticians.has(id);
    const trades = p.trade_count ?? 0;
    const tradeBadge = trades > 0
      ? `<span class="trade-count-badge">${trades} trades</span>`
      : `<span class="no-trades-badge">no trades</span>`;
    const chamberBadge = p.chamber
      ? `<span class="chamber-badge">${p.chamber}</span>`
      : '';
    return `
      <div class="pol-option${added ? ' already-added' : ''}" data-id="${id}">
        <span class="pol-option-name">${p.name}</span>
        <span class="party-badge ${partyClass(p.party)}">${partyLabel(p.party)}</span>
        ${chamberBadge}
        ${tradeBadge}
      </div>`;
  }).join('');

  dropdown.querySelectorAll('.pol-option:not(.already-added)').forEach(el => {
    el.addEventListener('click', e => {
      e.stopPropagation();
      const id = parseInt(el.dataset.id, 10);
      addPoliticianById(id);
      document.getElementById('polSearchInput').value = '';
      document.getElementById('polDropdown').classList.remove('open');
    });
  });
}

function wirePartyFilter() {
  document.getElementById('polPartyFilter').addEventListener('click', e => {
    const btn = e.target.closest('.party-filter-btn');
    if (!btn) return;
    document.querySelectorAll('.party-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentPartyFilter = btn.dataset.party;
    renderDropdownOptions(document.getElementById('polSearchInput').value);
  });
}

function wireSearchDropdown() {
  const input = document.getElementById('polSearchInput');
  const dropdown = document.getElementById('polDropdown');
  const wrap = document.getElementById('polSearchWrap');

  function openDropdown() {
    renderDropdownOptions(input.value);
    dropdown.classList.add('open');
  }

  input.addEventListener('focus', openDropdown);
  input.addEventListener('click', e => { e.stopPropagation(); openDropdown(); });
  input.addEventListener('input', openDropdown);

  document.addEventListener('click', e => {
    if (!wrap.contains(e.target)) {
      dropdown.classList.remove('open');
    }
  });
}

function addPoliticianById(id) {
  const pol = allPoliticians.find(p => (p.politician_id ?? p.id) === id);
  if (!pol || selectedPoliticians.has(id)) return;
  const colorIdx = selectedPoliticians.size % CHART_COLORS.length;
  selectedPoliticians.set(id, { id, name: pol.name, party: pol.party, color: CHART_COLORS[colorIdx] });
  renderSelectedPoliticians();
  refreshComparison();
}

function removePolitician(id) {
  selectedPoliticians.delete(id);
  renderSelectedPoliticians();
  refreshComparison();
  if (!selectedPoliticians.size) {
    document.getElementById('politicianDetail').style.display = 'none';
  }
}

function renderSelectedPoliticians() {
  const list = document.getElementById('polSelectedList');
  const hint = document.getElementById('polEmptyHint');
  // Refresh dropdown to reflect newly added/removed politicians
  const input = document.getElementById('polSearchInput');
  if (input) renderDropdownOptions(input.value);
  if (!selectedPoliticians.size) {
    list.innerHTML = '';
    list.appendChild(hint);
    return;
  }
  list.innerHTML = '';
  selectedPoliticians.forEach(pol => {
    const chip = document.createElement('div');
    chip.className = 'pol-chip';
    chip.dataset.id = pol.id;
    chip.innerHTML = `
      <span class="pol-dot" style="background:${pol.color}"></span>
      <span class="pol-chip-name">${pol.name}</span>
      <span class="pol-chip-party party-badge ${partyClass(pol.party)}">${partyLabel(pol.party)}</span>
      <button class="pol-chip-remove" title="Remove">✕</button>
    `;
    chip.querySelector('.pol-chip-remove').addEventListener('click', e => {
      e.stopPropagation();
      removePolitician(pol.id);
    });
    chip.addEventListener('click', () => loadPoliticianDetail(pol.id, pol.name, pol.party));
    list.appendChild(chip);
  });
}

async function loadPoliticianDetail(id, name, party) {
  const section = document.getElementById('politicianDetail');
  section.style.display = 'block';
  // Ensure body is expanded when switching politicians
  const body = document.getElementById('detailBody');
  const btn = document.getElementById('toggleDetail');
  body.style.display = '';
  btn.innerHTML = '&#x2212;';
  btn.title = 'Minimize';
  document.getElementById('detailName').textContent = `${name} · ${partyLabel(party)}`;

  const holdingsTbody = document.getElementById('holdingsBody');
  const tradesTbody = document.getElementById('tradesBody');
  holdingsTbody.innerHTML = '<tr><td colspan="5" class="loading">Loading…</td></tr>';
  tradesTbody.innerHTML = '<tr><td colspan="4" class="loading">Loading…</td></tr>';

  // Fetch portfolio and raw trades in parallel
  const [portfolioResult, tradesResult] = await Promise.allSettled([
    API.portfolio(id),
    API.trades(id),
  ]);

  // ── Holdings ──
  try {
    const portfolio = portfolioResult.status === 'fulfilled' ? portfolioResult.value : null;
    const holdings = portfolio?.holdings || [];

    const chip = document.querySelector(`.pol-chip[data-id="${id}"]`);
    if (chip) {
      chip.querySelector('.pol-no-data')?.remove();
      if (!holdings.length) {
        const badge = document.createElement('span');
        badge.className = 'pol-no-data';
        badge.title = 'No holdings data';
        badge.textContent = '∅';
        chip.querySelector('.pol-chip-name').after(badge);
      }
    }

    holdingsTbody.innerHTML = '';
    if (!holdings.length) {
      holdingsTbody.innerHTML = '<tr><td colspan="5" class="loading">No holdings data (prices may not be loaded yet).</td></tr>';
      renderAllocationChart([]);
    } else {
      holdings.forEach(h => {
        const pnl = h.unrealized_pnl ?? ((h.current_price - h.avg_cost) * h.shares);
        const cls = pnl >= 0 ? 'pos' : 'neg';
        const sign = pnl >= 0 ? '+' : '';
        holdingsTbody.insertAdjacentHTML('beforeend', `
          <tr>
            <td><strong>${h.ticker}</strong></td>
            <td>${h.shares.toFixed(2)}</td>
            <td>$${h.avg_cost.toFixed(2)}</td>
            <td>$${h.current_price.toFixed(2)}</td>
            <td class="${cls}">${sign}$${Math.abs(pnl).toFixed(0)}</td>
          </tr>
        `);
      });
      renderAllocationChart(holdings);
    }
  } catch (err) {
    holdingsTbody.innerHTML = `<tr><td colspan="5" class="loading">Error: ${err.message}</td></tr>`;
  }

  // ── Disclosed Trades ──
  try {
    const trades = tradesResult.status === 'fulfilled' ? tradesResult.value : [];
    tradesTbody.innerHTML = '';
    if (!trades.length) {
      tradesTbody.innerHTML = '<tr><td colspan="4" class="loading">No trades found.</td></tr>';
    } else {
      trades.forEach(t => {
        const isBuy = t.trade_type === 'BUY';
        const midpoint = (t.amount_from + t.amount_to) / 2;
        tradesTbody.insertAdjacentHTML('beforeend', `
          <tr>
            <td>${t.trade_date}</td>
            <td><strong>${t.ticker}</strong></td>
            <td><span class="badge ${isBuy ? 'badge-buy' : 'badge-sell'}">${t.trade_type}</span></td>
            <td>$${fmtMoney(t.amount_from)} – $${fmtMoney(t.amount_to)} (~$${fmtMoney(midpoint)})</td>
          </tr>
        `);
      });
    }
  } catch (err) {
    tradesTbody.innerHTML = `<tr><td colspan="4" class="loading">Error: ${err.message}</td></tr>`;
  }
}

/* ── Comparison chart ───────────────────────────────── */
async function refreshComparison() {
  const reqId = ++_compReqId;
  const hint = document.querySelector('#comparisonSection .hint');
  try {
    const ids = [...selectedPoliticians.keys()];
    const data = await API.comparison(currentBenchmark, currentRange, ids);
    if (reqId !== _compReqId) return; // discard stale response

    const polsWithColor = (data.politicians || []).map(p => ({
      ...p,
      color: selectedPoliticians.get(p.politician_id)?.color,
    }));

    const hasBenchData = (data.benchmark?.series || []).length > 0;
    const hasPolData = polsWithColor.some(p => (p.series || []).length > 0);

    if (!hasBenchData && !hasPolData) {
      if (hint) hint.textContent = 'No price data available — click ↻ Refresh Prices to load prices.';
    } else if (!hasBenchData) {
      if (hint) hint.textContent = `No price data for benchmark "${currentBenchmark}" — try ↻ Refresh Prices.`;
    } else if (ids.length > 0 && !hasPolData) {
      if (hint) hint.textContent = 'Benchmark loaded, but no portfolio price data for selected politicians — click ↻ Refresh Prices.';
    } else {
      if (hint) hint.textContent = '';
    }

    updateComparisonChart(data.benchmark, polsWithColor);
  } catch (err) {
    if (reqId !== _compReqId) return;
    console.warn('Comparison error:', err.message);
    if (hint) hint.textContent = `Chart error: ${err.message}`;
  }
}

/* ── Trade feed ─────────────────────────────────────── */
async function loadTradeFeed() {
  const feed = document.getElementById('tradeFeed');
  try {
    const trades = await API.recentTrades(50);
    feed.innerHTML = '';

    if (!trades.length) {
      feed.innerHTML = '<p class="loading">No trades yet — run the scraper first.</p>';
      return;
    }

    trades.forEach(t => {
      const isBuy = t.trade_type === 'BUY';
      feed.insertAdjacentHTML('beforeend', `
        <div class="trade-item">
          <span class="badge ${isBuy ? 'badge-buy' : 'badge-sell'}">${t.trade_type}</span>
          <span class="ticker">${t.ticker}</span>
          <span class="pol-name">${t.politician_name || '—'}</span>
          <span class="amount">~$${fmtMoney((t.amount_from + t.amount_to) / 2)}</span>
          <span class="date-tag">${t.trade_date}</span>
        </div>
      `);
    });
  } catch (err) {
    feed.innerHTML = `<p class="loading">Error: ${err.message}</p>`;
  }
}

/* ── Subscriptions ──────────────────────────────────── */
function populatePoliticianSelects() {
  const sel = document.getElementById('subPoliticianSelect');
  sel.innerHTML = '<option value="">— select politician —</option>';
  allPoliticians.forEach(p => {
    const id = p.politician_id ?? p.id;
    const label = `${p.name} (${partyLabel(p.party)})${(p.trade_count ?? 0) === 0 ? ' [no trades]' : ''}`;
    sel.insertAdjacentHTML('beforeend', `<option value="${id}">${label}</option>`);
  });
}

async function loadSubscriptions() {
  const list = document.getElementById('subList');
  try {
    const subs = await API.subscriptions();
    list.innerHTML = '';
    if (!subs.length) {
      list.innerHTML = '<li class="loading">No active subscriptions.</li>';
      return;
    }
    subs.forEach(s => {
      list.insertAdjacentHTML('beforeend', `
        <li>
          <span>Politician #${s.politician_id}</span>
          <span class="muted">→ Chat ${s.telegram_chat_id}</span>
          <span class="${s.active ? 'pos' : 'neg'}">${s.active ? 'Active' : 'Inactive'}</span>
          <button class="btn-danger" onclick="unsubscribe(${s.id})">Remove</button>
        </li>
      `);
    });
  } catch (err) {
    list.innerHTML = `<li class="loading">Error: ${err.message}</li>`;
  }
}

async function handleSubscribe() {
  const chatId = document.getElementById('chatIdInput').value.trim();
  const polId = parseInt(document.getElementById('subPoliticianSelect').value, 10);
  if (!chatId || !polId) { alert('Please fill in both fields.'); return; }
  try {
    await API.subscribe(polId, chatId);
    document.getElementById('chatIdInput').value = '';
    await loadSubscriptions();
  } catch (err) {
    alert(`Subscribe failed: ${err.message}`);
  }
}

async function unsubscribe(id) {
  try {
    await API.unsubscribe(id);
    await loadSubscriptions();
  } catch (err) {
    alert(`Unsubscribe failed: ${err.message}`);
  }
}

/* ── Leaderboard ────────────────────────────────────── */
async function loadLeaderboard() {
  const tbody = document.getElementById('leaderboardTbody');
  const sortBy = document.getElementById('leaderboardSort').value;
  tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading…</td></tr>';

  try {
    const rows = await API.get(`/api/leaderboard?sort_by=${sortBy}&limit=20`);

    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="loading">No data yet — refresh prices first.</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map((row, i) => {
      const returnCls = row.return_pct >= 0 ? 'pos' : 'neg';
      const returnSign = row.return_pct >= 0 ? '+' : '';
      const pnlCls = row.realized_pnl >= 0 ? 'pos' : 'neg';
      const pnlSign = row.realized_pnl >= 0 ? '+' : '';
      return `
        <tr class="leaderboard-row" data-id="${row.politician_id}" style="cursor:pointer">
          <td class="rank">${i + 1}</td>
          <td><strong>${row.name}</strong></td>
          <td><span class="party-badge ${partyClass(row.party)}">${partyLabel(row.party)}</span></td>
          <td>${row.chamber || '—'}</td>
          <td class="${returnCls}">${returnSign}${row.return_pct.toFixed(1)}%</td>
          <td>$${fmtMoney(row.current_value)}</td>
          <td class="${pnlCls}">${pnlSign}$${fmtMoney(Math.abs(row.realized_pnl))}</td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('.leaderboard-row').forEach(tr => {
      tr.addEventListener('click', () => {
        const id = parseInt(tr.dataset.id, 10);
        const row = rows.find(r => r.politician_id === id);
        if (!row) return;
        addPoliticianById(id);
        loadPoliticianDetail(id, row.name, row.party);
      });
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading">Error: ${err.message}</td></tr>`;
  }
}

/* ── Helpers ────────────────────────────────────────── */
const PARTY_LABELS = { D: 'Democrat', R: 'Republican', I: 'Independent' };
function partyLabel(code) { return PARTY_LABELS[code] ?? 'Other'; }
function partyClass(code) { return `party-${PARTY_LABELS[code] ? code : 'Other'}`; }

function fmtMoney(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(0) + 'K';
  return n.toFixed(0);
}
