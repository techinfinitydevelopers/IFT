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
    """Main form for idea submission"""
    
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
        help_text="Upload a video (optional, max 50MB)",
        widget=forms.FileInput(attrs={'accept': 'video/*', 'class': 'form-control'})
    )
    
    class Meta:
        model = IdeaSubmission
        fields = [
            'title',
            'description',
            'problem_statement',
            'target_audience',
            'innovation_aspect',
            'implementation_plan',
            'impact_assessment',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Give your idea a catchy title',
                'maxlength': 300
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe your idea in detail...',
                'rows': 5
            }),
            'problem_statement': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What problem does your idea solve?',
                'rows': 4
            }),
            'target_audience': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Who will benefit from your idea?',
                'rows': 3
            }),
            'innovation_aspect': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What makes your idea innovative and unique?',
                'rows': 4
            }),
            'implementation_plan': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'How do you plan to implement this idea?',
                'rows': 4
            }),
            'impact_assessment': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What impact will your idea have on society?',
                'rows': 4
            }),
        }
    
    def clean_video_file(self):
        """Validate video file size"""
        video = self.cleaned_data.get('video_file')
        if video:
            if video.size > 50 * 1024 * 1024:  # 50MB limit
                raise forms.ValidationError("Video file size must be under 50MB")
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
