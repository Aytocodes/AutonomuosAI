path = r'C:\Users\Tshepo Ayto\OneDrive\Documents\Visual studio code projects\html+css web\AutonomusAI_Web\frontend\index.html'

with open(path, encoding='utf-8') as f:
    content = f.read()

# Add tab CSS after .empty style
tab_css = """
  .empty { color: var(--muted); font-size: 0.85rem; text-align: center; padding: 20px; }

  /* ---- DASHBOARD TABS ---- */
  .dash-tabs { display: flex; gap: 4px; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 0; }
  .dash-tab { padding: 10px 20px; background: transparent; border: none; color: var(--muted); cursor: pointer; font-size: 0.88rem; font-weight: 600; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: all 0.2s; }
  .dash-tab:hover { color: var(--text); }
  .dash-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .dash-panel { display: none; }
  .dash-panel.active { display: block; }"""

content = content.replace(
    "  .empty { color: var(--muted); font-size: 0.85rem; text-align: center; padding: 20px; }",
    tab_css
)

# Add tabs HTML after <div class="main">
tabs_html = """  <div class="main">

    <!-- Dashboard Tabs -->
    <div class="dash-tabs">
      <button class="dash-tab active" onclick="switchTab('overview')">📊 Overview</button>
      <button class="dash-tab" onclick="switchTab('accounts')">🤖 Accounts</button>
      <button class="dash-tab" onclick="switchTab('charts')">📈 Charts</button>
      <button class="dash-tab" onclick="switchTab('logs')">📋 Logs</button>
    </div>

    <!-- TAB: Overview -->
    <div id="tab-overview" class="dash-panel active">"""

content = content.replace('  <div class="main">\n\n    <!-- Stats -->', tabs_html + '\n\n    <!-- Stats -->')

# Close overview tab and open accounts tab before accounts section
content = content.replace(
    '    <!-- Accounts + Add Form -->',
    '    </div><!-- end tab-overview -->\n\n    <!-- TAB: Accounts -->\n    <div id="tab-accounts" class="dash-panel">\n\n    <!-- Accounts + Add Form -->'
)

# Close accounts tab and open charts tab before charts section
content = content.replace(
    '    <!-- Profitability Charts -->',
    '    </div><!-- end tab-accounts -->\n\n    <!-- TAB: Charts -->\n    <div id="tab-charts" class="dash-panel">\n\n    <!-- Profitability Charts -->'
)

# Close charts tab and open logs tab before logs section
content = content.replace(
    '    <!-- Logs -->',
    '    </div><!-- end tab-charts -->\n\n    <!-- TAB: Logs -->\n    <div id="tab-logs" class="dash-panel">\n\n    <!-- Logs -->'
)

# Close logs tab before closing main div
content = content.replace(
    '  </div>\n</div>\n\n<!-- ================================================================ SCRIPT -->',
    '    </div><!-- end tab-logs -->\n\n  </div>\n</div>\n\n<!-- ================================================================ SCRIPT -->'
)

# Add switchTab JS function before showDashboard
switch_tab_js = """function switchTab(name) {
  document.querySelectorAll('.dash-tab').forEach((t, i) => {
    const names = ['overview','accounts','charts','logs'];
    t.classList.toggle('active', names[i] === name);
  });
  document.querySelectorAll('.dash-panel').forEach(p => {
    p.classList.toggle('active', p.id === 'tab-' + name);
  });
  if (name === 'charts') { loadAllChart(); }
  if (name === 'logs') {
    const id = document.getElementById('log-account-select')?.value;
    if (id) loadLogs();
  }
}

"""

content = content.replace('function showDashboard() {', switch_tab_js + 'function showDashboard() {')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('TABS ADDED')
