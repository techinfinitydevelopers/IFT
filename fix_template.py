import re

file_path = 'templates/admins/admin_dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix all == without spaces
content = re.sub(r"selected_category=='([^']+)'", r"selected_category == '\1'", content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed! Checking:')
import subprocess
result = subprocess.run(['powershell', 'Get-Content', file_path, '|', 'Select-String', 'selected_category'], capture_output=True, text=True)
print(result.stdout)
