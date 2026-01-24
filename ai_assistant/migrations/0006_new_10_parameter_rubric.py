# Generated manually for new 10-parameter evaluation rubric

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0005_add_mismatch_severity'),
    ]

    operations = [
        # Remove old score fields
        migrations.RemoveField(model_name='aievaluation', name='problem_clarity_score'),
        migrations.RemoveField(model_name='aievaluation', name='innovation_score'),
        migrations.RemoveField(model_name='aievaluation', name='feasibility_score'),
        migrations.RemoveField(model_name='aievaluation', name='impact_score'),
        migrations.RemoveField(model_name='aievaluation', name='explanation_quality_score'),
        migrations.RemoveField(model_name='aievaluation', name='idea_maturity_score'),
        
        # Remove old justification fields
        migrations.RemoveField(model_name='aievaluation', name='problem_clarity_justification'),
        migrations.RemoveField(model_name='aievaluation', name='innovation_justification'),
        migrations.RemoveField(model_name='aievaluation', name='feasibility_justification'),
        migrations.RemoveField(model_name='aievaluation', name='impact_justification'),
        migrations.RemoveField(model_name='aievaluation', name='explanation_quality_justification'),
        migrations.RemoveField(model_name='aievaluation', name='idea_maturity_justification'),
        
        # Remove mismatch fields (no longer used)
        migrations.RemoveField(model_name='aievaluation', name='attachment_mismatch'),
        migrations.RemoveField(model_name='aievaluation', name='mismatch_severity'),
        migrations.RemoveField(model_name='aievaluation', name='attachment_mismatch_reasons'),
        
        # Add new IDEA parameter score fields (1-5 scale)
        migrations.AddField(
            model_name='aievaluation',
            name='uniqueness_score',
            field=models.IntegerField(default=1, help_text='Uniqueness (1-5)'),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='ease_of_implementation_score',
            field=models.IntegerField(default=1, help_text='Ease of Implementation (1-5)'),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='scalable_score',
            field=models.IntegerField(default=1, help_text='Scalable (1-5)'),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='impactful_score',
            field=models.IntegerField(default=1, help_text='Impactful (1-5)'),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='sustainable_score',
            field=models.IntegerField(default=1, help_text='Sustainable (1-5)'),
        ),
        
        # Add new TEAM parameter score fields (1-5 scale)
        migrations.AddField(
            model_name='aievaluation',
            name='conceptual_clarity_score',
            field=models.IntegerField(default=1, help_text='Conceptual Clarity (1-5)'),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='empathy_score',
            field=models.IntegerField(default=1, help_text='Empathy (1-5)'),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='creativity_score',
            field=models.IntegerField(default=1, help_text='Creativity (1-5)'),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='communication_score',
            field=models.IntegerField(default=1, help_text='Communication (1-5)'),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='flexible_thinking_score',
            field=models.IntegerField(default=1, help_text='Flexible Thinking (1-5)'),
        ),
        
        # Add new justification fields
        migrations.AddField(
            model_name='aievaluation',
            name='uniqueness_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='ease_of_implementation_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='scalable_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='impactful_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='sustainable_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='conceptual_clarity_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='empathy_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='creativity_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='communication_justification',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aievaluation',
            name='flexible_thinking_justification',
            field=models.TextField(blank=True),
        ),
    ]
