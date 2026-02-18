from django import forms
from .models import LightSubmission, MentorScore


class LightSubmissionForm(forms.ModelForm):
    class Meta:
        model = LightSubmission
        fields = ['project_name', 'idea_description', 'industry', 'student_name']
        widgets = {
            'project_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Smart Water Monitor',
            }),
            'idea_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Short description of the idea...',
            }),
            'industry': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., EdTech, Health, Sustainability',
            }),
            'student_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Student name from the sheet',
            }),
        }


class MentorScoreForm(forms.ModelForm):
    class Meta:
        model = MentorScore
        fields = [
            'mentor_name',
            'uniqueness_score', 'ease_of_implementation_score', 'feasibility_score',
            'impactful_score', 'sustainable_score', 'conceptual_clarity_score',
            'empathy_score', 'creativity_score', 'communication_score',
            'flexible_thinking_score',
        ]
        widgets = {
            'mentor_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Rashida',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        score_fields = [
            'uniqueness_score', 'ease_of_implementation_score', 'feasibility_score',
            'impactful_score', 'sustainable_score', 'conceptual_clarity_score',
            'empathy_score', 'creativity_score', 'communication_score',
            'flexible_thinking_score',
        ]
        for field_name in score_fields:
            self.fields[field_name].widget = forms.NumberInput(attrs={
                'class': 'form-control score-input',
                'min': '0', 'max': '10', 'step': '1',
            })
