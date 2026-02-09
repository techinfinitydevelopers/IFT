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
    """Main form for idea submission - aligned with AI evaluation criteria"""
    
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
            'problem_definition',
            'problem_description',
            'target_user_group',
            'problem_urgency',
            'solution',
            'solution_benefits',
            'why_best_equipped',
            'idea_stage',
        ]
        widgets = {
            'problem_definition': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': "Define the problem precisely. What exactly is the issue you're trying to address?",
                'rows': 4
            }),
            'problem_description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Provide a detailed description of the problem. Include context, current situation, and scope.',
                'rows': 5
            }),
            'target_user_group': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': "Who are the users facing this problem? Describe their demographics, behavior, and characteristics.",
                'rows': 4
            }),
            'problem_urgency': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Why is this problem critical? What happens if it remains unsolved? What is the urgency?',
                'rows': 4
            }),
            'solution': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe your solution in detail. How does it work? What does it do?',
                'rows': 5
            }),
            'solution_benefits': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'How does your solution benefit users? What pain does it reduce or eliminate?',
                'rows': 4
            }),
            'why_best_equipped': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Why are you the best person/team to solve this? What unique skills, experience, or resources do you have?',
                'rows': 4
            }),
            'idea_stage': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'problem_definition': "1. It's always better to define the problem before we attempt to solve it. Be précised in articulating it.",
            'problem_description': '2. Give us a detailed description of the problem.',
            'target_user_group': "3. Describe the 'user' group whose problem you are attempting to solve?",
            'problem_urgency': '4. Why do you believe that this problem is critical and needs an urgent solution?',
            'solution': '5. What is your solution?',
            'solution_benefits': '6. How your solution gives a distinct benefit to users or reduce their pain?',
            'why_best_equipped': '7. Why do you think you are the best equipped to offer this solution?',
            'idea_stage': '8. Mention the stage of your idea at this moment',
        }
    
    def clean(self):
        """Validate that required question fields have meaningful content"""
        cleaned_data = super().clean()
        required_fields = {
            'problem_definition': 'Problem definition',
            'problem_description': 'Problem description',
            'target_user_group': 'Target user group',
            'problem_urgency': 'Problem urgency',
            'solution': 'Solution',
            'solution_benefits': 'Solution benefits',
            'why_best_equipped': 'Why best equipped',
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
            if video.size > 20 * 1024 * 1024:  # 20MB limit (matches Gemini API limit)
                raise forms.ValidationError("Video file size must be under 20MB")
        return video
    
    def clean_document_file(self):
        """Validate document file"""
        doc = self.cleaned_data.get('document_file')
        if doc:
            if doc.size > 10 * 1024 * 1024:  # 10MB limit
                raise forms.ValidationError("Document file size must be under 10MB")
        return doc
    
    def clean_image_file(self):
        """Validate image file"""
        img = self.cleaned_data.get('image_file')
        if img:
            if img.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError("Image file size must be under 5MB")
        return img

