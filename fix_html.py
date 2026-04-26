import re

path = r'C:\Users\Tshepo Ayto\OneDrive\Documents\Visual studio code projects\html+css web\AutonomusAI_Web\frontend\index.html'

with open(path, encoding='utf-8') as f:
    content = f.read()

# Fix 1: account name display - only show mt5_name if it's not generic
old1 = "        <div class=\"name\">${a.mt5_name ? a.mt5_name : a.broker_name} \u2014 ${a.account_login}</div>"
new1 = "        <div class=\"name\">${(a.mt5_name && a.mt5_name !== 'Demo Account' && a.mt5_name !== 'Real Account') ? a.mt5_name : a.broker_name} \u2014 ${a.account_login}</div>"

if old1 in content:
    content = content.replace(old1, new1)
    print('Fix 1: account name display - FIXED')
else:
    print('Fix 1: NOT FOUND')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
