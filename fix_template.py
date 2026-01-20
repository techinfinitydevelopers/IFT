import os

template_content = """{% extends 'base.html' %}
{% block title %}Jury Dashboard - IFT Platform{% endblock %}
{% block content %}
<div class="container py-3">
<h1>Jury Dashboard</h1>
<p class="text-muted">Review and evaluate student submissions</p>
<div class="grid grid-3 mt-2">
<div class="stat-card"><div class="stat-value">{{ total_submissions }}</div><div class="stat-label">Total Submissions</div></div>
<div class="stat-card"><div class="stat-value">{{ ai_processed_count }}</div><div class="stat-label">AI Processed</div></div>
<div class="stat-card"><div class="stat-value">{{ category_stats|length }}</div><div class="stat-label">Categories</div></div>
</div>
<div class="card mt-3">
<h3>Filter Submissions</h3>
<form method="get" style="display:flex;gap:1rem;align-items:end;">
<div style="flex:1;"><label class="form-label">Search</label><input type="text" name="search" class="form-control" placeholder="Title or student name..." value="{{ search_query }}"></div>
<div style="flex:1;"><label class="form-label">Category</label><select name="category" class="form-control"><option value="">All Categories</option><option value="edtech">EdTech</option><option value="sustainability">Sustainability</option><option value="health">Health & Wellness</option><option value="fintech">FinTech</option><option value="social_impact">Social Impact</option><option value="other">Other</option></select></div>
<button type="submit" class="btn btn-primary">Filter</button>
<a href="{% url 'admins:dashboard' %}" class="btn btn-outline">Clear</a>
</form>
</div>
<div class="mt-3">
<h2>Submissions</h2>
{% if submissions %}
<div class="grid">
{% for submission in submissions %}
<div class="card">
<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:1rem;">
<div><h3 style="margin:0;color:var(--primary-color);">{{ submission.title }}</h3><p class="text-muted" style="margin:0.5rem 0 0 0;font-size:0.875rem;">by {{ submission.student.user.get_full_name }} ({{ submission.student.student_id }})</p></div>
{% if submission.final_category %}<span class="badge badge-primary">{{ submission.get_final_category_display }}</span>{% endif %}
</div>
<p class="text-muted">{{ submission.description|truncatewords:30 }}</p>
{% if submission.ai_processed and submission.ai_summary %}<div style="background:rgba(99,102,241,0.1);padding:1rem;border-radius:8px;margin:1rem 0;border-left:3px solid var(--primary-color);"><div style="font-size:0.875rem;font-weight:600;color:var(--primary-color);margin-bottom:0.5rem;">🤖 AI Summary</div><p style="margin:0;color:var(--text-primary);line-height:1.5;">{{ submission.ai_summary.summary|truncatewords:35 }}</p></div>{% else %}<div style="background:rgba(245,158,11,0.1);padding:1rem;border-radius:8px;margin:1rem 0;border-left:3px solid var(--accent-color);"><p style="margin:0;color:var(--accent-color);font-size:0.9rem;">⏳ AI processing pending...</p></div>{% endif %}
<div style="display:flex;justify-content:space-between;align-items:center;margin-top:1rem;">
<span class="text-muted" style="font-size:0.875rem;">Submitted: {{ submission.submitted_at|date:"M d, Y" }}</span>
<a href="{% url 'admins:submission_detail' submission.id %}" class="btn btn-primary">Review Details</a>
</div>
</div>
{% endfor %}
</div>
{% else %}
<div class="card text-center" style="padding:3rem;"><div style="font-size:4rem;margin-bottom:1rem;">📋</div><h3>No submissions found</h3><p class="text-muted">Try adjusting your filters</p></div>
{% endif %}
</div>
</div>
{% endblock %}"""

with open('templates/admins/admin_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(template_content)
print("Fixed!")
