from django import forms
from django.contrib.auth.models import User
from .models import Student, IdeaSubmission, UploadedFile


class StudentRegistrationForm(forms.ModelForm):
    """Form for student registration"""
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput())
    password_confirm = forms.CharField(widget=forms.PasswordInput(), label="Confirm Password")
    
    class Meta:
        model = Student
        fields = ['school_name', 'grade', 'phone']
        widgets = {
            'school_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your School Name'}),
            'grade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Grade 10'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Number'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match")
        
        return cleaned_data


class IdeaSubmissionForm(forms.ModelForm):
    """Main form for idea submission — 12 questions aligned with AI evaluation criteria"""

    # File upload fields (not part of model, handled separately)
    document_file = forms.FileField(
        required=False,
        help_text="Upload a document or PPT (optional)",
        widget=forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.ppt,.pptx', 'class': 'form-control'})
    )
    image_file = forms.ImageField(
        required=False,
        help_text="Upload an image (optional)",
        widget=forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'})
    )
    video_file = forms.FileField(
        required=False,
        help_text="Upload a video (optional, max 20MB)",
        widget=forms.FileInput(attrs={'accept': 'video/*', 'class': 'form-control'})
    )

    class Meta:
        model = IdeaSubmission
        fields = [
            'title', 'competition_track',
            'q1_target_group', 'q2_exact_problem', 'q3_solution_simple',
            'q4_differentiation', 'q5_build_steps', 'q6_resources',
            'q7_positive_change', 'q8_challenges', 'q9_team_fit',
            'q10_feedback', 'q11_creative_element', 'q12_pitch',
        ]
        widgets = {
            'q1_target_group': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe the person or group you are trying to help. Who are they? What is their daily struggle related to this problem?',
                'rows': 4
            }),
            'q2_exact_problem': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What exact problem are they facing? When, where, and why does this problem matter? Why is it important to solve now?',
                'rows': 4
            }),
            'q3_solution_simple': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Explain your solution simply, as if you are talking to a 10-year-old.',
                'rows': 4
            }),
            'q4_differentiation': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'How is your solution different from what already exists or what people currently do to solve this problem?',
                'rows': 4
            }),
            'q5_build_steps': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What are the key steps required to build and test your solution in the real world?',
                'rows': 4
            }),
            'q6_resources': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What resources (skills, tools, money, technology, people) are required, and which of these do you already have?',
                'rows': 4
            }),
            'q7_positive_change': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'If your solution succeeds, what positive change will it create for users and society?',
                'rows': 4
            }),
            'q8_challenges': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What challenges or problems could come while building or using this idea? How will you deal with them?',
                'rows': 4
            }),
            'q9_team_fit': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Why do you think that your team is rightly placed to solve this problem than anyone else?',
                'rows': 4
            }),
            'q10_feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Have you taken any feedback from users on your idea? Describe one situation where your team changed its thinking or improved the idea after feedback or failure.',
                'rows': 4
            }),
            'q11_creative_element': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What is the most creative or unexpected element in your solution, and why did you think of it?',
                'rows': 4
            }),
            'q12_pitch': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'If you had 60 seconds to convince someone to try or support your idea, what would you say?',
                'rows': 4
            }),
        }
        labels = {
            'q1_target_group': "1. Describe the person or group you are trying to help. Who are they, and what is their daily struggle related to this problem?",
            'q2_exact_problem': "2. What exact problem are they facing? When, where, and why does this problem matter? Why is this problem important to solve now?",
            'q3_solution_simple': "3. What is your solution, explained simply as if you are talking to a 10-year-old?",
            'q4_differentiation': "4. How is your solution different from what already exists or what people currently do to solve this problem?",
            'q5_build_steps': "5. What are the key steps required to build and test your solution in the real world?",
            'q6_resources': "6. What resources (skills, tools, money, technology, people) are required, and which of these do you already have?",
            'q7_positive_change': "7. If your solution succeeds, what positive change will it create for users and society?",
            'q8_challenges': "8. What challenges or problems could come while building or using this idea? How will you deal with them?",
            'q9_team_fit': "9. Why do you think that your team is rightly placed to solve this problem than anyone else?",
            'q10_feedback': "10. Have you taken any feedback from users on your idea? Describe one situation where your team changed its thinking after feedback or failure.",
            'q11_creative_element': "11. What is the most creative or unexpected element in your solution, and why did you think of it?",
            'q12_pitch': "12. If you had 60 seconds to convince someone to try or support your idea, what would you say?",
        }

    def clean(self):
        """Validate that all 12 question fields have meaningful content"""
        cleaned_data = super().clean()
        required_fields = {
            'q1_target_group': 'Target group description',
            'q2_exact_problem': 'Problem description',
            'q3_solution_simple': 'Solution explanation',
            'q4_differentiation': 'Differentiation',
            'q5_build_steps': 'Build steps',
            'q6_resources': 'Resources',
            'q7_positive_change': 'Positive change',
            'q8_challenges': 'Challenges',
            'q9_team_fit': 'Team fit',
            'q10_feedback': 'Feedback & learning',
            'q11_creative_element': 'Creative element',
            'q12_pitch': '60-second pitch',
        }
        min_length = 20

        for field_name, label in required_fields.items():
            value = cleaned_data.get(field_name, '').strip()
            if not value:
                self.add_error(field_name, f'{label} is required.')
            elif len(value) < min_length:
                self.add_error(field_name, f'{label} must be at least {min_length} characters.')

        return cleaned_data

    def clean_video_file(self):
        """Validate video file size"""
        video = self.cleaned_data.get('video_file')
        if video:
            if video.size > 20 * 1024 * 1024:
                raise forms.ValidationError("Video file size must be under 20MB")
        return video

    def clean_document_file(self):
        """Validate document file"""
        doc = self.cleaned_data.get('document_file')
        if doc:
            if doc.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Document file size must be under 10MB")
        return doc

    def clean_image_file(self):
        """Validate image file"""
        img = self.cleaned_data.get('image_file')
        if img:
            if img.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file size must be under 5MB")
        return img

