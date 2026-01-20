# ENpower India Future Tycoon (IFT) Platform

A Django-based demo web application that allows students to submit innovation ideas and uses AI to generate neutral summaries to assist admins and jury members in the review process.

## 🎯 Key Features

- **Student Submission Portal**: Easy-to-use form for submitting innovation ideas with questionnaire responses and multimedia attachments
- **AI-Assisted Summaries**: Automatic generation of 2-3 sentence neutral summaries using OpenRouter (deepseek/deepseek-chat)
- **Category Tagging**: AI suggests relevant categories (EdTech, Sustainability, Health, etc.)
- **Jury Dashboard**: Clean interface for reviewing submissions with side-by-side AI summaries
- **Human-Led Decisions**: AI strictly does NOT score, evaluate, or shortlist ideas

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- OpenRouter API key (for AI features)

## 🚀 Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy the `.env.example` file to create your `.env` file:

```bash
copy .env.example .env
```

Edit `.env` and add your OpenRouter API key:

```
OPENROUTER_API_KEY=your_api_key_here
```

You can get an API key from [OpenRouter](https://openrouter.ai/).

### 3. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Create a Superuser (Admin Account)

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin account. This account will have access to both the Django admin panel and the Jury Dashboard.

### 5. Run the Development Server

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## 📖 Usage

### For Students

1. **Register**: Navigate to the home page and click "Register"
2. **Fill in Details**: Provide your information (name, school, grade)
3. **Submit Idea**: Click "Submit Idea" and fill out the comprehensive form
4. **Get AI Summary**: After submission, view the AI-generated neutral summary
5. **Track Submissions**: View all your submissions on your dashboard

### For Admins/Jury

1. **Login**: Use your superuser credentials to login
2. **Access Jury Panel**: Navigate to `/jury/` or click "Jury Panel" in the navbar
3. **Review Submissions**: Browse submissions with AI summaries
4. **Filter & Search**: Use category filters and search to find specific submissions
5. **View Details**: Click "Review Details" to see complete submission with side-by-side AI summary

### Admin Panel

Access the Django admin panel at `http://127.0.0.1:8000/admin/` to:
- Manage users and students
- View all submissions
- Manually update categories
- Review AI summaries and metadata

## 🔑 Key URLs

- `/` - Home page
- `/register/` - Student registration
- `/login/` - Student login
- `/dashboard/` - Student dashboard
- `/submit/` - Idea submission form
- `/jury/` - Jury dashboard (requires staff/superuser)
- `/admin/` - Django admin panel (requires superuser)

## 🤖 AI Integration

The platform uses OpenRouter API with the `deepseek/deepseek-chat` model to:

1. **Validate Submissions**: Check if all required fields are complete
2. **Generate Summaries**: Create neutral 2-3 sentence summaries
3. **Suggest Categories**: Tag submissions with relevant categories

**Important**: The AI is strictly configured to:
- ✅ Summarize and categorize ideas neutrally
- ❌ NOT score, evaluate, or shortlist ideas
- ❌ NOT make final decisions

All human jury members retain full control over evaluation and scoring.

## 🎨 Design Features

- **Modern UI**: Clean, minimal design with vibrant color palette
- **Responsive**: Works on desktop, tablet, and mobile devices
- **Progress Indicators**: Visual feedback during submission process
- **AI Disclaimers**: Clear notices that AI is assistive only
- **Accessible**: Semantic HTML and WCAG-compliant color contrast

## 📁 Project Structure

```
IFT/
├── ift_platform/          # Main Django project settings
├── students/              # Student module (submissions)
│   ├── models.py          # Student, IdeaSubmission, UploadedFile models
│   ├── forms.py           # Submission forms
│   ├── views.py           # Student views
│   └── urls.py            # Student URL routing
├── admins/                # Admin/jury module
│   ├── views.py           # Jury dashboard and review views
│   └── urls.py            # Admin URL routing
├── ai_assistant/          # AI integration
│   ├── models.py          # AISummary model
│   ├── openrouter_client.py  # OpenRouter API client
│   └── processors.py      # AI processing functions
├── templates/             # HTML templates
│   ├── base.html          # Base template
│   ├── students/          # Student templates
│   └── admins/            # Admin templates
├── static/                # Static files
│   └── css/
│       └── styles.css     # Main stylesheet
├── media/                 # User uploads
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
└── manage.py              # Django management script
```

## 🛡️ Security Notes

- The default `SECRET_KEY` in settings.py is for development only
- Change it in production via the `.env` file
- Never commit your `.env` file or API keys to version control
- File uploads are validated for size and type
- User authentication is required for submissions and jury access

## 🐛 Troubleshooting

**AI Processing Fails**:
- Check that `OPENROUTER_API_KEY` is set in `.env`
- Verify API key is valid at OpenRouter
- Check error details in the admin panel under AI Summaries

**Static Files Not Loading**:
- Run `python manage.py collectstatic` if deploying to production
- Make sure `DEBUG=True` in development

**Database Issues**:
- Delete `db.sqlite3` and run migrations again
- Check file permissions

## 📝 License

This is a demo application for the ENpower India Future Tycoon platform.

## 🤝 Contributing

This is a demonstration project. For production use, consider:
- Switching to PostgreSQL or MySQL
- Adding proper user roles and permissions
- Implementing email notifications
- Adding automated testing
- Setting up proper error logging
- Deploying to a production server

## 📧 Support

For questions or issues with the IFT platform, please contact the development team.

---

**Built with Django, OpenRouter AI, and ❤️**
