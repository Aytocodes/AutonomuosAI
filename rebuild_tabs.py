path = r'C:\Users\Tshepo Ayto\OneDrive\Documents\Visual studio code projects\html+css web\AutonomusAI_Web\frontend\index.html'

with open(path, encoding='utf-8') as f:
    content = f.read()

# ── 1. Inject tab CSS before </style>
tab_css = """
  /* ---- DASHBOARD TABS ---- */
  .dash-tabs { display:flex; gap:2px; margin-bottom:24px; border-bottom:1px solid var(--border); }
  .dash-tab { padding:10px 22px; background:transparent; border:none; border-bottom:2px solid transparent;
              color:var(--muted); cursor:pointer; font-size:0.88rem; font-weight:600; margin-bottom:-1px; transition:all 0.2s; }
  .dash-tab:hover { color:var(--text); }
  .dash-tab.active { color:var(--accent); border-bottom-color:var(--accent); }
  .dash-panel { display:none; }
  .dash-panel.active { display:block; }
  /* Account detail card */
  .acc-detail { background:var(--card); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin-bottom:16px; }
  .acc-detail-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
  .acc-detail-name { font-size:1.05rem; font-weight:700; }
  .acc-detail-sub { font-size:0.78rem; color:var(--muted); margin-top:2px; }
  .acc-meta { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:14px; }
  .acc-meta-item { background:var(--bg); border-radius:6px; padding:10px; text-align:center; }
  .acc-meta-item .lbl { font-size:0.68rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.05em; }
  .acc-meta-item .val { font-size:1rem; font-weight:700; margin-top:3px; }
  .open-trades { margin-top:10px; }
  .open-trade-row { display:flex; justify-content:space-between; align-items:center; padding:6px 10px;
                    background:var(--bg); border-radius:6px; margin-bottom:4px; font-size:0.78rem; }
  .open-trade-row .sym { font-weight:700; color:var(--accent); }
  .open-trade-row .dir-buy { color:var(--green); }
  .open-trade-row .dir-sell { color:var(--red); }
  .open-trade-row .pnl.pos { color:var(--green); }
  .open-trade-row .pnl.neg { color:var(--red); }
</style>"""

content = content.replace('</style>', tab_css)

# ── 2. Replace the entire dashboard main section
old_main_start = '  <div class="main">'
new_main = '''  <div class="main">

    <!-- Dashboard Tabs -->
    <div class="dash-tabs">
      <button class="dash-tab active" onclick="switchTab('overview')">&#128202; Overview</button>
      <button class="dash-tab" onclick="switchTab('accounts')">&#129302; Accounts</button>
      <button class="dash-tab" onclick="switchTab('charts')">&#128200; Charts</button>
      <button class="dash-tab" onclick="switchTab('logs')">&#128203; Logs</button>
    </div>

    <!-- ===== TAB: OVERVIEW ===== -->
    <div id="tab-overview" class="dash-panel active">
      <div class="stats-row">
        <div class="stat-card"><div class="label">Total Accounts</div><div class="value blue" id="stat-accounts">0</div></div>
        <div class="stat-card"><div class="label">Active Accounts</div><div class="value green" id="stat-active">0</div></div>
        <div class="stat-card"><div class="label">Running Bots</div><div class="value green" id="stat-running">0</div></div>
        <div class="stat-card"><div class="label">Total Trades Today</div><div class="value blue" id="stat-trades">0</div></div>
      </div>
      <div class="bot-control">
        <div class="bot-status">
          <div class="status-dot" id="global-dot"></div>
          <div>
            <div style="font-weight:600" id="global-status-text">Bot Stopped</div>
            <div style="font-size:0.78rem;color:var(--muted)"></div>
          </div>
          <div class="algo-badge" id="algo-badge"><div class="algo-dot"></div>ALGO TRADING ON</div>
        </div>
        <div style="display:flex;align-items:center;gap:16px">
          <canvas id="trading-canvas" width="180" height="44"></canvas>
          <div class="bot-btns">
            <button class="btn green sm" onclick="startAllBots()">&#9654; Start All</button>
            <button class="btn red sm" onclick="stopAllBots()">&#9632; Stop All</button>
            <button class="btn sm" onclick="refreshAll()">&#8635; Refresh</button>
          </div>
        </div>
      </div>
      <!-- Account cards with balance + open trades -->
      <div id="accounts-overview"></div>
    </div>

    <!-- ===== TAB: ACCOUNTS ===== -->
    <div id="tab-accounts" class="dash-panel">
      <div class="grid-2">
        <div>
          <div class="section-title">Trading Accounts</div>
          <div class="accounts-list" id="accounts-list"><div class="empty">No accounts added yet</div></div>
        </div>
        <div>
          <div class="section-title">Add Account</div>
          <div class="add-form">
            <div class="form-group"><label>Broker Name</label><input type="text" id="add-broker" placeholder="Exness, ICMarkets..."></div>
            <div class="form-row">
              <div class="form-group"><label>Account Login</label><input type="text" id="add-login" placeholder="12345678"></div>
              <div class="form-group"><label>Password</label><input type="password" id="add-pass" placeholder="&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;"></div>
            </div>
            <div class="form-group"><label>Server</label><input type="text" id="add-server" placeholder="Exness-MT5Real"></div>
            <div class="form-group"><label>Risk per Trade (%)</label><input type="number" id="add-risk" value="1" min="0.1" max="50" step="0.1"></div>
            <button class="btn" onclick="addAccount()">Add Account</button>
            <div class="error-msg" id="add-error"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== TAB: CHARTS ===== -->
    <div id="tab-charts" class="dash-panel">
      <div class="grid-2">
        <div class="chart-box">
          <div class="chart-toolbar">
            <div style="display:flex;flex-direction:column;gap:6px">
              <div class="section-title" style="margin:0">Account Profitability</div>
              <select id="chart-account-select" onchange="loadAccountChart()"><option value="">Select account...</option></select>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px">
              <div class="chart-stats">
                <div class="chart-stat">Net: <span id="acc-chart-net">&#8212;</span></div>
                <div class="chart-stat">Trades: <span id="acc-chart-trades">&#8212;</span></div>
                <div class="chart-stat">Best: <span id="acc-chart-best" class="pos">&#8212;</span></div>
                <div class="chart-stat">Worst: <span id="acc-chart-worst" class="neg">&#8212;</span></div>
              </div>
              <div class="period-btns">
                <button class="period-btn" onclick="setAccPeriod('week')">By Day</button>
                <button class="period-btn active" onclick="setAccPeriod('month')">By Month</button>
                <button class="period-btn" onclick="setAccPeriod('year')">By Year</button>
              </div>
            </div>
          </div>
          <canvas id="acc-profit-chart" height="140"></canvas>
        </div>
        <div class="chart-box">
          <div class="chart-toolbar">
            <div>
              <div class="section-title" style="margin:0">Overall Profitability</div>
              <div style="font-size:0.75rem;color:var(--muted);margin-top:2px">All accounts &#8212; USD</div>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px">
              <div class="chart-stats">
                <div class="chart-stat">Net: <span id="all-chart-net">&#8212;</span></div>
                <div class="chart-stat">Trades: <span id="all-chart-trades">&#8212;</span></div>
                <div class="chart-stat">Best: <span id="all-chart-best" class="pos">&#8212;</span></div>
                <div class="chart-stat">Worst: <span id="all-chart-worst" class="neg">&#8212;</span></div>
              </div>
              <div class="period-btns">
                <button class="period-btn" onclick="setAllPeriod('week')">By Day</button>
                <button class="period-btn active" onclick="setAllPeriod('month')">By Month</button>
                <button class="period-btn" onclick="setAllPeriod('year')">By Year</button>
              </div>
            </div>
          </div>
          <canvas id="all-profit-chart" height="140"></canvas>
        </div>
      </div>
    </div>

    <!-- ===== TAB: LOGS ===== -->
    <div id="tab-logs" class="dash-panel">
      <div class="section-title">Trade Logs</div>
      <div class="logs-box">
        <select class="log-select" id="log-account-select" onchange="loadLogs()"><option value="">Select account...</option></select>
        <div class="log-list" id="log-list"><div class="empty">Select an account to view logs</div></div>
      </div>
    </div>

  </div>
</div>'''

# Find the dashboard main div and replace everything from <div class="main"> to </div>\n</div>
import re
pattern = r'  <div class="main">.*?  </div>\n</div>'
if re.search(pattern, content, re.DOTALL):
    content = re.sub(pattern, new_main, content, flags=re.DOTALL)
    print('Main section replaced')
else:
    print('Pattern not found')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('DONE')
