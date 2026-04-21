const API = {
  async get(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
    return res.json();
  },

  async post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async del(path) {
    const res = await fetch(path, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) throw new Error(`${res.status} ${res.statusText}`);
  },

  politicians:   ()             => API.get('/api/politicians'),
  trades:        (id)           => API.get(`/api/politicians/${id}/trades`),
  portfolio:     (id)           => API.get(`/api/politicians/${id}/portfolio`),
  leaderboard:   (sortBy = 'return_pct', limit = 20) => API.get(`/api/leaderboard?sort_by=${sortBy}&limit=${limit}`),
  comparison:    (ticker, range, ids) =>
    API.get(`/api/comparison?ticker=${encodeURIComponent(ticker)}&range=${range}&politician_ids=${ids.join(',')}`),
  recentTrades:  (limit = 50)   => API.get(`/api/trades/recent?limit=${limit}`),
  benchmarks:    ()             => API.get('/api/benchmarks'),
  updatePrices:  ()             => API.post('/api/admin/update-prices', {}),
  enrichParties: ()             => API.post('/api/admin/enrich-parties', {}),
  subscribe:     (politician_id, telegram_chat_id) =>
    API.post('/api/subscriptions', { politician_id, telegram_chat_id }),
  subscriptions: ()             => API.get('/api/subscriptions'),
  unsubscribe:   (id)           => API.del(`/api/subscriptions/${id}`),
};
