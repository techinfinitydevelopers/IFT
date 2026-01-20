# IFT Platform - Demo Guide

## 🎯 What to Do Next

Now that you're logged in to the admin panel, here's the complete workflow to test all features of the IFT Platform:

---

## Step 1: Register as a Student 🎓

Since you need a student account to submit ideas, let's create one:

1. **Open a new browser tab or use incognito mode** (so you can stay logged in as admin)
2. Navigate to: `http://127.0.0.1:8001/register/`
3. Fill out the registration form:
   - **Username**: `student1` (or any username you like)
   - **Email**: `student1@school.com`
   - **First Name**: Your first name
   - **Last Name**: Your last name
   - **Password**: Create a password
   - **Confirm Password**: Same password
   - **School Name**: Your school name
   - **Grade**: Your grade (e.g., Grade 10)
   - **Phone** (optional): Contact number

4. Click "Register" - you'll be automatically logged in as the student

---

## Step 2: Submit an Innovation Idea 💡

Now as a student, submit a test idea:

1. After registration, you'll see your student dashboard
2. Click **"Submit Your Idea"** or navigate to `/submit/`
3. Fill out the comprehensive submission form:

### Required Fields:

**Basic Information:**
- **Title**: e.g., "EcoLearn - Sustainable Education Platform"
- **Description**: Detailed description of your idea (at least a few sentences)

**Questionnaire:**
- **Problem Statement**: What problem does your idea solve?
- **Target Audience**: Who will benefit from your idea?
- **Innovation Aspect**: What makes your idea innovative?
- **Implementation Plan**: How do you plan to implement this?
- **Impact Assessment**: What impact will your idea have?

**Supporting Materials (Optional):**
- **Document/PPT**: Upload a PDF or PowerPoint
- **Image**: Upload a relevant image
- **Video**: Upload a video file (max 50MB)

4. Click **"Submit Idea"**

---

## Step 3: View AI-Generated Summary ��

After submission:

1. You'll be redirected to the **Confirmation Page**
2. The AI will automatically:
   - ✅ Validate your submission for completeness
   - ✅ Generate a neutral 2-3 sentence summary
   - ✅ Suggest category tags (EdTech, Sustainability, etc.)
   - ✅ Display processing metadata

3. You'll see:
   - Your submission details
   - AI-generated summary in a blue card
   - Suggested categories as badges
   - **Clear disclaimer**: "AI-generated summary is for assistance only"

---

## Step 4: Review as Admin/Jury 👨‍⚖️

Now go back to your admin browser tab:

1. Navigate to: `http://127.0.0.1:8001/jury/` or click "Jury Panel" in the navbar
2. You'll see the **Jury Dashboard** with:
   - **Statistics**: Total submissions, AI processed count
   - **Filter Controls**: Search by title/name, filter by category
   - **Submission Cards**: Each showing:
     - Student name and ID
     - Idea title and description preview
     - AI-generated summary
     - Submission date
     - "Review Details" button

3. Click **"Review Details"** on any submission to see:
   - **Left Side**: Complete submission details
     - Student information
     - All questionnaire responses
     - Uploaded files
   - **Right Side (Sticky)**: AI Summary panel
     - AI-generated summary
     - Suggested category tags
     - Completeness status
     - Processing metadata (model, tokens, time)
     - AI disclaimer

---

## Step 5: Explore Additional Features 🔍

### Django Admin Panel

Access at `http://127.0.0.1:8001/admin/`:
- Manage all users and students
- View/edit all submissions
- Review AI summaries and metadata
- Manual override of categories

### Student Dashboard

As a student at `http://127.0.0.1:8001/dashboard/`:
- View all your submissions
- Track submission status
- See AI summaries for your ideas
- Submit new ideas

### Filters & Search

On the Jury Dashboard:
- **Search**: Type keywords to find specific submissions
- **Category Filter**: Select a category to filter submissions
- **Clear**: Reset all filters

---

## 🤖 Understanding AI Integration

### What the AI Does:
- ✅ Generates neutral 2-3 sentence summaries
- ✅ Suggests relevant category tags
- ✅ Validates submission completeness
- ✅ Extracts text from uploaded files (conceptually)

### What the AI Does NOT Do:
- ❌ Score or evaluate ideas
- ❌ Shortlist submissions
- ❌ Make final decisions
- ❌ Approve or reject ideas

**All decisions remain with human jury members!**

---

## 📋 Testing Checklist

- [ ] Register a student account
- [ ] Submit at least one idea  with all fields filled
- [ ] Verify AI summary is generated
- [ ] Check AI-suggested categories appear
- [ ] View submission in jury dashboard
- [ ] Use search functionality
- [ ] Filter by category
- [ ] Review detailed submission view
- [ ] Verify AI disclaimer appears everywhere
- [ ] Test file uploads (optional)

---

## 🎨 Design Features to Notice

1. **Clean, Modern UI**
   - Dark theme with purple/blue gradients
   - Card-based layouts
   - Smooth shadows and hover effects
   - Professional Inter font

2. **Progress Indicators**
   - Visual feedback during submission
   - Step-by-step guidance

3. **AI Disclaimers**
   - Present on every AI summary
   - Clear messaging about AI's role
   - Emphasis on human control

4. **Responsive Design**
   - Works on desktop, tablet, mobile
   - Flexible grid layouts
   - Mobile-friendly forms

---

## 🔧 Configuration

### OpenRouter API Key

To enable real AI summaries (currently using mock data if no API key):

1. Get an API key from [OpenRouter](https://openrouter.ai/)
2. Copy `.env.example` to `.env`
3. Add your key: `OPENROUTER_API_KEY=your_key_here`
4. Restart the server

### Database

Currently using SQLite (`db.sqlite3`). For production:
- Use PostgreSQL or MySQL
- Update `DATABASE` settings in `settings.py`

---

## 📞 Need Help?

- **Server not running?** Check that port 8001 is free
- **Template errors?** Check the console output
- **AI not working?** Verify API key in `.env`  
- **Login issues?** Use credentials: `admin` / `IFTadmin2026!`

---

## 🎉 Enjoy Testing!

The platform is fully functional and ready to demonstrate how AI can **assist** (not replace) human judgment in reviewing innovation ideas!
