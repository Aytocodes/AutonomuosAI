path = r'C:\Users\Tshepo Ayto\OneDrive\Documents\Visual studio code projects\html+css web\AutonomusAI_Web\frontend\index.html'

with open(path, encoding='utf-8') as f:
    content = f.read()

new_js = '''function switchTab(name) {
  document.querySelectorAll('.dash-tab').forEach(t => {
    const map = {'overview':0,'accounts':1,'charts':2,'logs':3};
    const tabs = ['overview','accounts','charts','logs'];
    t.classList.toggle('active', t.textContent.toLowerCase().includes(tabs[map[name]]?.slice(0,4) || name));
  });
  document.querySelectorAll('.dash-panel').forEach(p => {
    p.classList.toggle('active', p.id === 'tab-' + name);
  });
  if (name === 'charts') { loadAllChart(); }
  if (name === 'logs') { const id = document.getElementById('log-account-select')?.value; if (id) loadLogs(); }
  if (name === 'overview') loadAccountOverview();
}

async function loadAccountOverview() {
  const wrap = document.getElementById('accounts-overview');
  if (!wrap) return;
  if (!accounts.length) { wrap.innerHTML = '<div class="empty">No accounts added yet</div>'; return; }
  wrap.innerHTML = accounts.map(a => `
    <div class="acc-detail">
      <div class="acc-detail-header">
        <div>
          <div class="acc-detail-name">${(a.mt5_name && a.mt5_name !== 'Demo Account') ? a.mt5_name : a.broker_name} &mdash; ${a.account_login}</div>
          <div class="acc-detail-sub">${a.broker_name} | ${a.server || 'No server'} | Risk: ${(a.risk_pct*100).toFixed(1)}% | Strategy: ${(a.strategy||'both').toUpperCase()}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <button id="algo-btn-${a.id}" class="btn sm green" onclick="toggleBot(${a.id})" title="Start Trading">&#9654;</button>
          <button class="btn sm" onclick="verifyAccount(${a.id})">&#10003; Verify</button>
        </div>
      </div>
      <div class="acc-meta" id="meta-${a.id}">
        <div class="acc-meta-item"><div class="lbl">Balance</div><div class="val" id="bal-${a.id}">--</div></div>
        <div class="acc-meta-item"><div class="lbl">Equity</div><div class="val" id="eq-${a.id}">--</div></div>
        <div class="acc-meta-item"><div class="lbl">Open Trades</div><div class="val" id="ot-${a.id}">--</div></div>
      </div>
      <div class="open-trades" id="trades-${a.id}"></div>
    </div>
  `).join('');

  // Fetch live data for each running account
  for (const a of accounts) {
    try {
      const info = await api('GET', `/accounts/${a.id}/info`);
      document.getElementById(`bal-${a.id}`).textContent = `${info.currency} ${info.balance.toFixed(2)}`;
      document.getElementById(`eq-${a.id}`).textContent  = `${info.currency} ${info.equity.toFixed(2)}`;
    } catch(e) {
      document.getElementById(`bal-${a.id}`).textContent = 'Start bot first';
    }
    try {
      const pos = await api('GET', `/accounts/${a.id}/positions`);
      document.getElementById(`ot-${a.id}`).textContent = pos.length;
      const tradesEl = document.getElementById(`trades-${a.id}`);
      if (pos.length) {
        tradesEl.innerHTML = pos.map(p => `
          <div class="open-trade-row">
            <span class="sym">${p.symbol}</span>
            <span class="${p.direction==='buy'?'dir-buy':'dir-sell'}">${p.direction.toUpperCase()}</span>
            <span>Lot: ${p.volume}</span>
            <span>Entry: ${p.open_price}</span>
            <span class="pnl ${p.profit>=0?'pos':'neg'}">${p.profit>=0?'+':''}${p.profit.toFixed(2)}</span>
          </div>`).join('');
      } else {
        tradesEl.innerHTML = '<div style="font-size:0.75rem;color:var(--muted);padding:6px 0">No open trades</div>';
      }
    } catch(e) {
      document.getElementById(`ot-${a.id}`).textContent = '--';
    }
  }
}

'''

content = content.replace('function showDashboard() {', new_js + 'function showDashboard() {')

# Fix switchTab to work properly with button text
content = content.replace(
    "  document.querySelectorAll('.dash-tab').forEach(t => {\n    const map = {'overview':0,'accounts':1,'charts':2,'logs':3};\n    const tabs = ['overview','accounts','charts','logs'];\n    t.classList.toggle('active', t.textContent.toLowerCase().includes(tabs[map[name]]?.slice(0,4) || name));\n  });",
    "  document.querySelectorAll('.dash-tab').forEach(t => {\n    t.classList.toggle('active', t.getAttribute('onclick').includes(\"'\" + name + \"'\"));\n  });"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('JS INJECTED')
