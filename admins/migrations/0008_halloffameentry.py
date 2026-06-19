from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admins', '0007_evaluatorassignment_is_shortlisted'),
    ]

    operations = [
        migrations.CreateModel(
            name='HallOfFameEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', models.ImageField(blank=True, help_text='Student/team photo (optional)', null=True, upload_to='halloffame/')),
                ('student_name', models.CharField(max_length=300)),
                ('school_name', models.CharField(max_length=300)),
                ('idea_title', models.CharField(max_length=300)),
                ('idea_description', models.TextField(blank=True, help_text='Short description shown on card')),
                ('problem_statement', models.TextField(blank=True)),
                ('proposed_solution', models.TextField(blank=True)),
                ('tags', models.JSONField(default=list, help_text="List of SDG tag strings e.g. ['SDG 11 - Sustainable Cities']")),
                ('rank', models.PositiveIntegerField(help_text='1-24')),
                ('season', models.CharField(default='Season 5', help_text='e.g. Season 5', max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['rank'],
            },
        ),
    ]
