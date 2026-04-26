path = r'C:\Users\Tshepo Ayto\OneDrive\Documents\Visual studio code projects\html+css web\AutonomusAI_Web\frontend\index.html'

with open(path, encoding='utf-8') as f:
    content = f.read()

old = """function showDashboard() {
  document.getElementById('auth-page').style.display  = 'none';
  document.getElementById('dashboard').style.display  = 'block';
  document.getElementById('nav-user').textContent = USER?.email || USER?.phone || 'User';
  loadAccounts();
  loadAllChart();
  refreshStatus();
  statusInterval = setInterval(refreshStatus, 3000);
}"""

new = """function showDashboard() {
  document.getElementById('auth-page').style.display  = 'none';
  document.getElementById('dashboard').style.display  = 'block';
  document.getElementById('nav-user').textContent = USER?.email || USER?.phone || 'User';
  loadAccounts().then(() => loadAccountOverview());
  refreshStatus();
  statusInterval = setInterval(refreshStatus, 3000);
}"""

if old in content:
    content = content.replace(old, new)
    print('showDashboard fixed')
else:
    print('NOT FOUND')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('DONE')
