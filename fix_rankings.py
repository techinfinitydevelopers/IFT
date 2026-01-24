import os

content = '''{% extends 'base.html' %}
{% block title %}Rankings - Jury Dashboard{% endblock %}

{% block content %}
<style>
.tabs { display: flex; gap: 0; margin-bottom: 0; border-bottom: 2px solid var(--border); }
.tab { padding: 0.75rem 1.5rem; cursor: pointer; border: none; background: transparent; font-size: 1rem; font-weight: 600; color: var(--text-muted); border-bottom: 3px solid transparent; margin-bottom: -2px; transition: all 0.2s; }
.tab:hover { color: var(--text-body); background: var(--bg-surface-active); }
.tab.active { color: var(--primary); border-bottom-color: var(--primary); }
.tab-content { display: none; }
.tab-content.active { display: block; }
</style>

<div class="container mt-4">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
        <h1 style="font-size: 1.5rem; margin: 0;">🏆 Rankings Leaderboard</h1>
        <div>
            <a href="{% url 'admins:export_top_400' %}" class="btn btn-success btn-sm">📥 Export Top 400 CSV</a>
            <a href="{% url 'admins:dashboard' %}" class="btn btn-outline-secondary btn-sm" style="margin-left: 0.5rem;">← Back</a>
        </div>
    </div>

    <div class="grid" style="grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem;">
        <div class="card" style="background: var(--primary); color: white;">
            <h4 style="font-size: 0.9rem; margin-bottom: 0.5rem;">Total Evaluated</h4>
            <div style="font-size: 2rem; font-weight: 700;">{{ total_evaluated }}</div>
        </div>
        <div class="card" style="background: var(--success); color: white;">
            <h4 style="font-size: 0.9rem; margin-bottom: 0.5rem;">Top 400</h4>
            <div style="font-size: 2rem; font-weight: 700;">{{ top_400_count }}</div>
        </div>
        <div class="card" style="background: #f59e0b;">
            <h4 style="font-size: 0.9rem; margin-bottom: 0.5rem;">Normal Ranking</h4>
            <div style="font-size: 2rem; font-weight: 700;">{{ normal_count }}</div>
        </div>
        <div class="card" style="background: var(--info); color: white;">
            <h4 style="font-size: 0.9rem; margin-bottom: 0.5rem;">Batch Evaluate</h4>
            <form method="post" action="{% url 'admins:batch_evaluate' %}">{% csrf_token %}<input type="hidden" name="limit" value="10"><button type="submit" class="btn btn-outline-light btn-sm">Evaluate Next 10</button></form>
        </div>
    </div>

    <div class="card">
        <div class="tabs">
            <button class="tab active" onclick="showTab('top400')">🥇 Top 400 Rankings ({{ top_400_count }})</button>
            <button class="tab" onclick="showTab('normal')">📋 Normal Rankings ({{ normal_count }})</button>
        </div>

        <div id="top400" class="tab-content active" style="padding: 1rem 0;">
            <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 1rem;">✅ Ideas scoring above 37/50 (75% threshold).</p>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: rgba(16, 185, 129, 0.15); border-bottom: 2px solid var(--success);">
                            <th style="padding: 0.75rem; text-align: left;">Rank</th>
                            <th style="padding: 0.75rem; text-align: left;">Score</th>
                            <th style="padding: 0.75rem; text-align: left;">Title</th>
                            <th style="padding: 0.75rem; text-align: left;">Student</th>
                            <th style="padding: 0.75rem; text-align: center;">Unique</th>
                            <th style="padding: 0.75rem; text-align: center;">Ease</th>
                            <th style="padding: 0.75rem; text-align: center;">Scale</th>
                            <th style="padding: 0.75rem; text-align: center;">Impact</th>
                            <th style="padding: 0.75rem; text-align: center;">Sustain</th>
                            <th style="padding: 0.75rem; text-align: center;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for e in top_400_evaluations %}
                        <tr style="border-bottom: 1px solid var(--border);">
                            <td style="padding: 0.75rem;"><strong>#{{ e.rank }}</strong> <span class="badge badge-success" style="font-size: 0.7rem;">Top 400</span></td>
                            <td style="padding: 0.75rem;"><span class="badge badge-success" style="font-size: 1rem;">{{ e.final_score }}/50</span></td>
                            <td style="padding: 0.75rem;"><a href="{% url 'admins:submission_detail' e.submission.id %}">{{ e.submission.title|truncatechars:30 }}</a></td>
                            <td style="padding: 0.75rem;">{{ e.submission.student.user.get_full_name|default:e.submission.student.user.username }}</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.uniqueness_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.ease_of_implementation_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.scalable_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.impactful_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.sustainable_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;"><a href="{% url 'admins:submission_detail' e.submission.id %}" class="btn btn-outline-primary btn-sm">View</a></td>
                        </tr>
                        {% empty %}
                        <tr><td colspan="10" style="padding: 2rem; text-align: center; color: var(--text-muted);">No ideas qualify for Top 400 yet (need score > 37/50).</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div id="normal" class="tab-content" style="padding: 1rem 0;">
            <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 1rem;">⚠️ Ideas scoring 37/50 or below.</p>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: rgba(245, 158, 11, 0.15); border-bottom: 2px solid #f59e0b;">
                            <th style="padding: 0.75rem; text-align: left;">Score</th>
                            <th style="padding: 0.75rem; text-align: left;">Title</th>
                            <th style="padding: 0.75rem; text-align: left;">Student</th>
                            <th style="padding: 0.75rem; text-align: center;">Unique</th>
                            <th style="padding: 0.75rem; text-align: center;">Ease</th>
                            <th style="padding: 0.75rem; text-align: center;">Scale</th>
                            <th style="padding: 0.75rem; text-align: center;">Impact</th>
                            <th style="padding: 0.75rem; text-align: center;">Sustain</th>
                            <th style="padding: 0.75rem; text-align: center;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for e in normal_evaluations %}
                        <tr style="border-bottom: 1px solid var(--border);">
                            <td style="padding: 0.75rem;"><span class="badge {% if e.final_score >= 30 %}badge-warning{% else %}badge-danger{% endif %}" style="font-size: 1rem;">{{ e.final_score }}/50</span></td>
                            <td style="padding: 0.75rem;"><a href="{% url 'admins:submission_detail' e.submission.id %}">{{ e.submission.title|truncatechars:30 }}</a></td>
                            <td style="padding: 0.75rem;">{{ e.submission.student.user.get_full_name|default:e.submission.student.user.username }}</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.uniqueness_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.ease_of_implementation_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.scalable_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.impactful_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;">{{ e.sustainable_score }}/5</td>
                            <td style="padding: 0.75rem; text-align: center;"><a href="{% url 'admins:submission_detail' e.submission.id %}" class="btn btn-outline-primary btn-sm">View</a></td>
                        </tr>
                        {% empty %}
                        <tr><td colspan="9" style="padding: 2rem; text-align: center; color: var(--text-muted);">No submissions in normal rankings.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
function showTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    event.target.classList.add('active');
}
</script>
{% endblock %}
'''

with open('templates/admins/rankings.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('File written successfully')
