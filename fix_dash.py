import os

file_path = 'templates/admins/admin_dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix all the template syntax issues
replacements = [
    ("selected_category=='edtech'", "selected_category == 'edtech'"),
    ("selected_category=='sustainability'", "selected_category == 'sustainability'"),
    ("selected_category=='health'", "selected_category == 'health'"),
    ("selected_category=='fintech'", "selected_category == 'fintech'"),
    ("selected_category=='social_impact'", "selected_category == 'social_impact'"),
    ("selected_category=='agriculture'", "selected_category == 'agriculture'"),
    ("selected_category=='other'", "selected_category == 'other'"),
]

for old, new in replacements:
    content = content.replace(old, new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed! Verify with:')
print(open(file_path).read()[1000:1800])
