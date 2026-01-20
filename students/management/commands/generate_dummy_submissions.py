"""
Django management command to generate dummy submissions with actual files.
This command safely creates test data without breaking existing functionality.
"""

import os
import shutil
import random
from io import BytesIO
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from students.models import Student, IdeaSubmission, UploadedFile
from ai_assistant.models import AISummary


class Command(BaseCommand):
    help = 'Generate dummy submissions with images, PDFs, and videos for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=3,
            help='Number of submissions to create (default: 3)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing dummy submissions before creating new ones'
        )

    def handle(self, *args, **options):
        count = options['count']
        clear = options['clear']
        
        if clear:
            self.stdout.write('Clearing existing dummy submissions...')
            self.clear_dummy_data()
        
        self.stdout.write(f'Creating {count} dummy submissions...')
        
        # Create or get dummy students
        students = self.create_dummy_students(count)
        
        # Submission data
        submissions_data = self.get_submissions_data()
        
        # Create submissions
        for i, (student, sub_data) in enumerate(zip(students, submissions_data[:count])):
            submission = self.create_submission(student, sub_data)
            self.create_files_for_submission(submission, sub_data['files'])
            self.create_ai_summary(submission, sub_data)
            self.stdout.write(self.style.SUCCESS(f'Created submission: {submission.title}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully created {count} dummy submissions!'))
        self.stdout.write('\nSummary:')
        self.stdout.write(f'  - Students created: {count}')
        self.stdout.write(f'  - Submissions created: {count}')
        self.stdout.write(f'  - AI Summaries created: {count}')
        self.stdout.write(f'  - Files attached: {count * 3} (1 image, 1 PDF, 1 video per submission)')

    def clear_dummy_data(self):
        """Remove existing dummy data"""
        dummy_users = User.objects.filter(username__startswith='dummy_student_')
        count = dummy_users.count()
        dummy_users.delete()
        self.stdout.write(f'  Removed {count} dummy users and their data')

    def create_dummy_students(self, count):
        """Create dummy student accounts"""
        students = []
        schools = [
            'Delhi Public School, New Delhi',
            'Kendriya Vidyalaya, Mumbai',
            'DAV Public School, Chennai',
            'Ryan International School, Bangalore',
            'St. Xavier\'s High School, Kolkata',
        ]
        grades = ['9th', '10th', '11th', '12th']
        
        for i in range(count):
            username = f'dummy_student_{i+1}'
            
            # Check if user already exists
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@example.com',
                    'first_name': ['Arjun', 'Priya', 'Rahul', 'Sneha', 'Vikram'][i % 5],
                    'last_name': ['Sharma', 'Patel', 'Gupta', 'Singh', 'Kumar'][i % 5],
                }
            )
            
            if created:
                user.set_password('demopass123')
                user.save()
            
            student, _ = Student.objects.get_or_create(
                user=user,
                defaults={
                    'student_id': f'IFT2026{str(i+1).zfill(4)}',
                    'school_name': schools[i % len(schools)],
                    'grade': grades[i % len(grades)],
                    'phone': f'98765{str(43210 + i).zfill(5)}',
                }
            )
            students.append(student)
        
        return students

    def get_submissions_data(self):
        """Return detailed submission data"""
        return [
            {
                'title': 'EcoTrack - Smart Waste Management System',
                'category': 'sustainability',
                'description': '''EcoTrack is an innovative IoT-based smart waste management system designed to revolutionize how cities handle waste collection. Our solution uses low-cost ultrasonic sensors installed in waste bins to monitor fill levels in real-time.

The data is transmitted via LoRaWAN to a cloud-based platform where AI algorithms analyze patterns and optimize collection routes for garbage trucks. This reduces unnecessary trips, saves fuel, and ensures bins never overflow.

Key features include:
- Real-time monitoring dashboard for municipal authorities
- Mobile app for residents to report issues
- Predictive analytics for demand forecasting
- Integration with existing municipal systems
- Carbon footprint tracking and reporting''',
                'problem_statement': '''Urban areas in India generate over 62 million tonnes of waste annually, yet collection systems remain inefficient. Traditional fixed-schedule collection leads to:
- Overflowing bins causing health hazards
- Unnecessary fuel consumption on empty runs
- Inconsistent service quality across neighborhoods
- No visibility into actual waste generation patterns

Our research in 3 tier-1 cities showed that 40% of collection trips are suboptimal, and citizen complaints about waste management rank among the top 5 municipal grievances.''',
                'target_audience': '''Our primary target segments include:
1. Municipal Corporations (Smart City initiatives)
2. Large Housing Societies (500+ units)
3. Commercial Complexes and IT Parks
4. Educational Institutions
5. Industrial Estates

Initial focus: Tier-1 cities with existing smart city budgets (₹48,000 crore allocated under Smart Cities Mission).''',
                'innovation_aspect': '''EcoTrack stands out through:
1. Cost Innovation: Our sensor costs ₹800 vs ₹5,000 for imported alternatives
2. Connectivity: LoRaWAN works in areas with poor cellular coverage
3. AI-Powered: Machine learning predicts fill rates with 92% accuracy
4. Local Manufacturing: Made in India, reducing dependencies
5. Modular Design: Retrofits to existing bins without replacement''',
                'implementation_plan': '''Phase 1 (Months 1-3): Pilot in Dwarka, New Delhi
- Deploy 100 smart sensors across 5 wards
- Partner with SDMC for data integration
- Train 20 collection staff on new system

Phase 2 (Months 4-9): Scale to 1000 bins
- Expand based on pilot learnings
- Launch citizen mobile app
- Integrate with Swachh Bharat dashboard

Phase 3 (Year 2): Multi-city expansion
- Replicate in 5 more cities
- Establish local manufacturing unit
- Target 10,000 sensor deployments''',
                'impact_assessment': '''Projected Impact (Year 1):
- 30% reduction in collection vehicle fuel costs
- 40% decrease in overflow incidents
- 25% improvement in collection efficiency
- 500 tonnes CO2 emissions saved

Social Impact:
- Cleaner neighborhoods improving quality of life
- Reduced disease vectors from overflowing waste
- Employment for 50+ local technicians''',
                'files': {
                    'image': ('concept_diagram.png', 'ecotrack_diagram'),
                    'pdf': 'business_plan',
                    'video': 'demo_video'
                }
            },
            {
                'title': 'MediConnect - Telemedicine for Rural India',
                'category': 'health',
                'description': '''MediConnect bridges the healthcare gap between rural and urban India through an innovative telemedicine platform. Our mobile-first solution enables villagers to consult with qualified doctors through video calls, even on basic 2G networks.

The platform features:
- Low-bandwidth video consultation (works on 2G)
- Support for 10 Indian languages
- Integration with Jan Aushadhi stores for medicine delivery
- Offline prescription storage
- ASHA worker assisted consultations
- AI-powered symptom checker for triage''',
                'problem_statement': '''India faces a severe healthcare access crisis:
- 70% population lives in rural areas
- Only 30% of healthcare infrastructure is rural
- Doctor-to-patient ratio: 1:1456 (vs WHO recommended 1:1000)
- Average travel for specialist: 50+ km

Consequences:
- Delayed diagnoses leading to complications
- High out-of-pocket expenses on travel
- Lost wages for daily workers
- Preventable deaths due to delayed care''',
                'target_audience': '''Primary Users:
1. Rural patients (500M+ potential users)
2. ASHA workers (1M+ across India)
3. PHC staff needing specialist consultations
4. Urban doctors seeking to expand reach

Geographic Focus: States with lowest doctor density - UP, Bihar, MP, Rajasthan, Jharkhand (combined population: 400M+)''',
                'innovation_aspect': '''Technical Innovations:
1. Adaptive Streaming: Automatically switches between video/audio/text based on network
2. Regional Language AI: Symptom checker in Hindi, Tamil, Telugu, Bengali
3. Offline-First: Critical features work without internet
4. ASHA Integration: Trained health workers assist with devices

Business Model Innovation:
- Freemium for basic consultations
- Subscription for chronic disease management
- B2G contracts with state health departments''',
                'implementation_plan': '''Phase 1: MVP Launch (3 months)
- Develop Android app with 3 language support
- Onboard 50 doctors across specialties
- Partner with 5 PHCs in Rajasthan
- Train 100 ASHA workers

Phase 2: Expansion (6 months)
- Add 5 more languages
- Integrate medicine delivery
- Launch AI symptom checker
- Reach 10,000 consultations/month

Phase 3: Scale (Year 2)
- Expand to 5 states
- Partner with PMJAY for insurance
- Target 100,000 monthly consultations''',
                'impact_assessment': '''Health Impact:
- Reduce travel time from 4 hours to 15 minutes
- Enable 1000+ daily consultations
- Decrease treatment delays by 80%
- Improve medication adherence through reminders

Economic Impact:
- Save ₹500-1000 per consultation in travel
- Create income for 500+ rural health assistants
- Generate ₹50L+ annual revenue by Year 2''',
                'files': {
                    'image': ('app_mockup.png', 'mediconnect_app'),
                    'pdf': 'technical_specs',
                    'video': 'pitch_video'
                }
            },
            {
                'title': 'AgriDrone - AI-Powered Crop Monitoring',
                'category': 'agriculture',
                'description': '''AgriDrone democratizes precision agriculture for small and marginal farmers through affordable drone-based crop monitoring. Our solution uses multispectral imaging and AI to detect crop diseases, pest infestations, and irrigation issues before they become visible to the naked eye.

Features:
- Low-cost modular drone kit (under ₹50,000)
- Smartphone-based analysis app
- WhatsApp integration for alerts
- Regional language support
- Drone-as-a-Service rental model''',
                'problem_statement': '''Indian agriculture challenges:
- 86% farmers are small/marginal (< 2 hectares)
- 15-25% annual crop losses to pests and diseases
- Inefficient water usage (40% wastage)
- Limited access to expert advisory

Current precision agriculture tools cost ₹5-10 lakhs, making them inaccessible to 90% of farmers. Late detection of crop issues leads to ₹90,000 crore annual losses.''',
                'target_audience': '''Target Segments:
1. Farmer Producer Organizations (7,000+ FPOs)
2. Progressive small farmers (5M+ farmers)
3. Agricultural cooperatives
4. State agriculture departments
5. Agricultural universities

Initial Focus: Punjab, Haryana, Maharashtra (high-value crops, tech-savvy farmers)''',
                'innovation_aspect': '''What makes AgriDrone unique:
1. Affordability: 10x cheaper than existing solutions
2. Simplicity: WhatsApp-based alerts, no training needed
3. AI Accuracy: 95%+ accuracy in disease detection
4. Local Crops: Trained on Indian crop varieties
5. Service Model: Pay-per-use eliminates ownership burden

Technical Edge:
- Custom lightweight drone frame
- Multispectral camera with 5 bands
- Edge AI processing on smartphone
- Satellite imagery fusion for large farms''',
                'implementation_plan': '''Phase 1: Prototype & Pilot (4 months)
- Build 10 production drones
- Partner with 3 FPOs in Punjab
- Cover 500 acres in pilot
- Validate AI accuracy on wheat, rice, cotton

Phase 2: Commercial Launch (8 months)
- Launch Drone-as-a-Service at ₹500/acre
- Expand to 5,000 acres coverage
- Add 5 more crop types
- Train 50 local drone operators

Phase 3: Scale (Year 2)
- Expand to Maharashtra and Haryana
- Target 50,000 acres coverage
- Launch farmer franchise model
- Seek NABARD partnership''',
                'impact_assessment': '''Agricultural Impact:
- 20% yield improvement through early detection
- 30% water savings via precision irrigation
- 50% reduction in pesticide usage
- ₹10,000-15,000 savings per acre annually

Environmental Impact:
- Reduced chemical runoff
- Lower carbon footprint vs traditional scouting
- Biodiversity protection through targeted spraying

Social Impact:
- Employment for 100+ rural youth as operators
- Farmer income improvement
- Reduced farm distress''',
                'files': {
                    'image': ('drone_monitoring.png', 'agridrone_monitoring'),
                    'pdf': 'financial_projections',
                    'video': 'prototype_demo'
                }
            },
            # FAKE/INCONSISTENT SUBMISSION - For testing AI consistency check
            {
                'title': 'SolarGrid - Community Solar Energy Platform',
                'category': 'sustainability',
                'is_fake': True,  # Flag for special handling
                'description': '''SolarGrid is a revolutionary community-based solar energy sharing platform that enables neighborhoods to collectively invest in, install, and share benefits from rooftop solar installations. Our platform uses blockchain for transparent energy credit distribution.

Key features include:
- Peer-to-peer energy trading within community
- AI-powered load balancing
- Mobile wallet for solar credits
- Smart inverter integration
- Carbon offset certificates''',
                'problem_statement': '''India receives 300+ sunny days annually but solar adoption remains low:
- High upfront costs (₹3-5 lakhs for home installation)
- Complex approval processes
- Lack of awareness about net metering
- No mechanism for renters to benefit from solar

Only 2% of India's rooftop potential is currently utilized, representing a massive missed opportunity for clean energy.''',
                'target_audience': '''Primary Users:
1. Urban housing societies (50,000+ societies)
2. Commercial building owners
3. Environmentally conscious renters
4. Small businesses with high electricity bills

Geographic Focus: High-irradiance states - Rajasthan, Gujarat, Maharashtra, Karnataka''',
                'innovation_aspect': '''SolarGrid's unique approach:
1. Fractional Solar Ownership: Buy shares starting at ₹5,000
2. Blockchain Credits: Transparent, tradeable energy tokens
3. Community Model: Shared infrastructure, shared benefits
4. Smart Matching: AI matches surplus producers with consumers
5. Zero Hassle: We handle installation, maintenance, approvals''',
                'implementation_plan': '''Phase 1: MVP Launch (3 months)
- Launch platform with 5 pilot societies in Pune
- Install 500 kW community solar capacity
- Develop mobile app for energy tracking

Phase 2: Scale (6 months)
- Expand to 50 societies
- Add blockchain-based credit system
- Launch corporate B2B partnerships

Phase 3: National Rollout (Year 2)
- Target 500 societies across 10 cities
- Achieve 50 MW installed capacity
- IPO preparation''',
                'impact_assessment': '''Environmental Impact:
- 100,000 tonnes CO2 offset annually by Year 3
- Equivalent to planting 5 million trees

Economic Impact:
- 30% electricity bill savings for participants
- ₹50 crore community investment mobilized
- 500+ green jobs created''',
                'files': {
                    'image': ('solar_platform.png', 'food_delivery_app'),  # MISMATCH!
                    'pdf': 'solar_business_plan',
                    'video': 'solar_demo'
                }
            }
        ]

    def create_submission(self, student, data):
        submission = IdeaSubmission.objects.create(
            student=student,
            title=data['title'],
            description=data['description'],
            problem_statement=data['problem_statement'],
            target_audience=data['target_audience'],
            innovation_aspect=data['innovation_aspect'],
            implementation_plan=data['implementation_plan'],
            impact_assessment=data['impact_assessment'],
            ai_suggested_category=data['category'],
            final_category=data['category'],
            status='submitted',
            submitted_at=timezone.now(),
            ai_processed=True,
        )
        return submission

    def create_files_for_submission(self, submission, files_info):
        """Create and attach files to submission"""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        # Image file
        image_filename, image_source = files_info['image']
        self.create_image_file(submission, image_filename, image_source, base_path)
        
        # PDF file
        pdf_name = files_info['pdf']
        self.create_pdf_file(submission, f'{pdf_name}.pdf', base_path)
        
        # Video file
        video_name = files_info['video']
        self.create_video_file(submission, f'{video_name}.mp4', base_path)

    def create_image_file(self, submission, filename, source_name, base_path):
        """Create image file attachment"""
        # Source images generated by AI (stored in .gemini folder)
        source_images = {
            'ecotrack_diagram': 'C:/Users/kunal/.gemini/antigravity/brain/46f3895d-be4c-4794-bf24-a01e2cc97a73/ecotrack_diagram_1768564648747.png',
            'mediconnect_app': 'C:/Users/kunal/.gemini/antigravity/brain/46f3895d-be4c-4794-bf24-a01e2cc97a73/mediconnect_app_1768564667576.png',
            'agridrone_monitoring': 'C:/Users/kunal/.gemini/antigravity/brain/46f3895d-be4c-4794-bf24-a01e2cc97a73/agridrone_monitoring_1768564685214.png',
            'food_delivery_app': 'C:/Users/kunal/.gemini/antigravity/brain/46f3895d-be4c-4794-bf24-a01e2cc97a73/food_delivery_app_1768567836601.png',
        }
        
        source_path = source_images.get(source_name)
        if source_path and os.path.exists(source_path):
            with open(source_path, 'rb') as f:
                content = f.read()
            
            uploaded = UploadedFile.objects.create(
                submission=submission,
                file_type='image',
                original_filename=filename,
                file_size=len(content),
                extracted_text=f'Diagram showing {submission.title} concept and architecture.'
            )
            uploaded.file.save(filename, ContentFile(content))
            self.stdout.write(f'    ✓ Added image: {filename}')
        else:
            # Create placeholder image
            self.create_placeholder_image(submission, filename)

    def create_placeholder_image(self, submission, filename):
        """Create a placeholder image if source not found"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a placeholder image
            img = Image.new('RGB', (800, 600), color=(52, 73, 94))
            draw = ImageDraw.Draw(img)
            
            # Add text
            text = f"{submission.title}\n\nConcept Diagram"
            draw.multiline_text((400, 300), text, fill=(255, 255, 255), anchor='mm')
            
            # Save to bytes
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            content = buffer.getvalue()
            
            uploaded = UploadedFile.objects.create(
                submission=submission,
                file_type='image',
                original_filename=filename,
                file_size=len(content),
            )
            uploaded.file.save(filename, ContentFile(content))
            self.stdout.write(f'    ✓ Added placeholder image: {filename}')
        except ImportError:
            self.stdout.write(self.style.WARNING(f'    ⚠ PIL not installed, skipping image: {filename}'))

    def create_pdf_file(self, submission, filename, base_path):
        """Create a PDF file attachment"""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.units import inch
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                textColor=colors.HexColor('#2C3E50')
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                textColor=colors.HexColor('#3498DB')
            )
            
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=12,
                leading=16
            )
            
            story = []
            
            # Title
            story.append(Paragraph(submission.title, title_style))
            story.append(Spacer(1, 20))
            
            # Category
            story.append(Paragraph(f"Category: {submission.get_final_category_display()}", body_style))
            story.append(Spacer(1, 20))
            
            # Sections
            sections = [
                ('Executive Summary', submission.description[:500] + '...'),
                ('Problem Statement', submission.problem_statement),
                ('Target Audience', submission.target_audience),
                ('Innovation Aspect', submission.innovation_aspect),
                ('Implementation Plan', submission.implementation_plan),
                ('Impact Assessment', submission.impact_assessment),
            ]
            
            for title, content in sections:
                story.append(Paragraph(title, heading_style))
                # Clean the content for PDF
                clean_content = content.replace('\n', '<br/>')
                story.append(Paragraph(clean_content, body_style))
                story.append(Spacer(1, 15))
            
            doc.build(story)
            content = buffer.getvalue()
            
            uploaded = UploadedFile.objects.create(
                submission=submission,
                file_type='document',
                original_filename=filename,
                file_size=len(content),
                extracted_text=f'{submission.description}\n\n{submission.problem_statement}\n\n{submission.innovation_aspect}'
            )
            uploaded.file.save(filename, ContentFile(content))
            self.stdout.write(f'    ✓ Added PDF: {filename}')
            
        except ImportError:
            # Create minimal PDF without reportlab
            self.create_minimal_pdf(submission, filename)

    def create_minimal_pdf(self, submission, filename):
        """Create a minimal valid PDF without external libraries"""
        # Basic PDF structure
        content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 200 >>
stream
BT
/F1 24 Tf
50 700 Td
({submission.title[:50]}) Tj
/F1 12 Tf
0 -30 Td
(Category: {submission.final_category}) Tj
0 -20 Td
(Status: {submission.status}) Tj
0 -20 Td
(This is a demo document for testing purposes.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000518 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
595
%%EOF"""
        
        content_bytes = content.encode('latin-1')
        
        uploaded = UploadedFile.objects.create(
            submission=submission,
            file_type='document',
            original_filename=filename,
            file_size=len(content_bytes),
            extracted_text=f'{submission.title}\n{submission.description[:200]}'
        )
        uploaded.file.save(filename, ContentFile(content_bytes))
        self.stdout.write(f'    ✓ Added minimal PDF: {filename}')

    def create_video_file(self, submission, filename, base_path):
        """Create a video file attachment (placeholder MP4)"""
        try:
            # Try to create a minimal valid MP4 file
            # This is a tiny valid MP4 file (ftyp + moov atoms)
            mp4_header = bytes([
                # ftyp atom
                0x00, 0x00, 0x00, 0x20,  # size: 32 bytes
                0x66, 0x74, 0x79, 0x70,  # type: 'ftyp'
                0x69, 0x73, 0x6F, 0x6D,  # major_brand: 'isom'
                0x00, 0x00, 0x00, 0x01,  # minor_version: 1
                0x69, 0x73, 0x6F, 0x6D,  # compatible_brands: 'isom'
                0x61, 0x76, 0x63, 0x31,  # compatible_brands: 'avc1'
                0x6D, 0x70, 0x34, 0x31,  # compatible_brands: 'mp41'
                0x6D, 0x70, 0x34, 0x32,  # compatible_brands: 'mp42'
                # Minimal moov atom
                0x00, 0x00, 0x00, 0x08,  # size: 8 bytes
                0x6D, 0x6F, 0x6F, 0x76,  # type: 'moov'
            ])
            
            uploaded = UploadedFile.objects.create(
                submission=submission,
                file_type='video',
                original_filename=filename,
                file_size=len(mp4_header),
                extracted_text=f'Demo video for {submission.title}. Duration: 2 minutes. Content: Product demonstration and team pitch.'
            )
            uploaded.file.save(filename, ContentFile(mp4_header))
            self.stdout.write(f'    ✓ Added video placeholder: {filename}')
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'    ⚠ Could not create video: {e}'))

    def create_ai_summary(self, submission, data):
        """Create AI Summary for the submission"""
        
        # Generate AI summary based on submission data
        ai_summaries = {
            'EcoTrack - Smart Waste Management System': {
                'summary': 'EcoTrack proposes an innovative IoT-based smart waste management solution that leverages ultrasonic sensors and LoRaWAN connectivity to monitor bin fill levels in real-time. The system employs AI algorithms to optimize garbage collection routes, potentially reducing fuel costs by 30% and overflow incidents by 40%. The solution demonstrates strong alignment with Smart Cities Mission objectives and presents a viable business model targeting municipal corporations.',
                'tags': ['sustainability', 'technology', 'social_impact'],
                'file_summaries': {
                    'concept_diagram.png': 'System architecture diagram showing the complete EcoTrack ecosystem including smart sensors, cloud connectivity via LoRaWAN, AI-powered analytics platform, and mobile applications for both citizens and municipal staff. The diagram effectively illustrates data flow from sensors through cloud processing to actionable route optimization.',
                    'business_plan.pdf': 'Comprehensive business document outlining the EcoTrack value proposition, market analysis targeting ₹48,000 crore Smart Cities budget, competitive pricing at ₹800 per sensor vs ₹5,000 imports, and a phased implementation plan starting with 100 bins in Dwarka, Delhi.',
                    'demo_video.mp4': 'Product demonstration video showcasing the EcoTrack sensor installation process, real-time monitoring dashboard, and route optimization visualization. The video effectively communicates the system\'s ease of deployment and immediate value proposition.'
                },
                'is_consistent': True,
                'inconsistency_reasons': [],
                'is_complete': True,
                'completeness_notes': 'The submission is comprehensive with clear problem definition, innovative solution approach, detailed implementation plan, and quantifiable impact metrics.'
            },
            'MediConnect - Telemedicine for Rural India': {
                'summary': 'MediConnect addresses India\'s rural healthcare crisis through a mobile-first telemedicine platform optimized for low-bandwidth environments. The solution\'s key innovation lies in its adaptive streaming technology that works on 2G networks, combined with multi-language support and ASHA worker integration. The platform targets 500M+ potential rural users and proposes partnerships with state health departments for sustainable scale.',
                'tags': ['health', 'technology', 'social_impact'],
                'file_summaries': {
                    'app_mockup.png': 'Professional UI mockup showing MediConnect\'s telemedicine interface featuring video consultation screen, prescription management, and language selection supporting Hindi, Tamil, and other regional languages. The design emphasizes accessibility and simplicity for rural users.',
                    'technical_specs.pdf': 'Technical specification document detailing the adaptive streaming architecture, offline-first design principles, AI-powered symptom checker, and integration points with Jan Aushadhi stores for medicine delivery.',
                    'pitch_video.mp4': 'Team pitch video presenting MediConnect\'s mission to bridge the healthcare gap, featuring testimonials and demonstration of the app\'s low-bandwidth video consultation capability.'
                },
                'is_consistent': True,
                'inconsistency_reasons': [],
                'is_complete': True,
                'completeness_notes': 'Well-structured submission with clear understanding of rural healthcare challenges and a technically sound solution approach.'
            },
            'AgriDrone - AI-Powered Crop Monitoring': {
                'summary': 'AgriDrone democratizes precision agriculture through affordable drone-based crop monitoring, addressing the critical challenge of 15-25% annual crop losses faced by India\'s 86% small and marginal farmers. The solution combines multispectral imaging with edge AI processing on smartphones, achieving 95%+ disease detection accuracy at 10x lower cost than existing solutions. The Drone-as-a-Service model at ₹500/acre effectively eliminates ownership barriers.',
                'tags': ['agriculture', 'technology', 'sustainability'],
                'file_summaries': {
                    'drone_monitoring.png': 'Visualization showing AgriDrone in operation over farmland with NDVI heat map overlay displaying crop health variations. The image demonstrates the multispectral analysis capabilities and intuitive color-coded health indicators for farmers.',
                    'financial_projections.pdf': 'Financial model projecting ₹10,000-15,000 savings per acre annually for farmers, with detailed cost breakdown of the ₹50,000 drone kit and revenue projections for the service model targeting 50,000 acres by Year 2.',
                    'prototype_demo.mp4': 'Prototype demonstration video showing the AgriDrone in flight, capturing multispectral imagery, and the smartphone app analyzing crop health with disease detection alerts.'
                },
                'is_consistent': True,
                'inconsistency_reasons': [],
                'is_complete': True,
                'completeness_notes': 'Strong submission with innovative approach to making precision agriculture accessible to small farmers through service-based model.'
            },
            # FAKE/INCONSISTENT SUBMISSION
            'SolarGrid - Community Solar Energy Platform': {
                'summary': 'SolarGrid proposes a community-based solar energy sharing platform using blockchain for energy credit distribution. While the written proposal describes a solar energy solution, careful analysis reveals significant inconsistencies between the submission content and attached materials.',
                'tags': ['sustainability', 'fintech', 'technology'],
                'file_summaries': {
                    'solar_platform.png': '⚠️ INCONSISTENCY DETECTED: The uploaded image shows a food delivery mobile application interface (similar to Swiggy/Zomato) with restaurant listings, food menus, and delivery tracking - completely unrelated to the solar energy platform described in the submission.',
                    'solar_business_plan.pdf': 'Business document discussing solar energy implementation, community solar investment model, and blockchain-based credit system. Content aligns with submission description.',
                    'solar_demo.mp4': 'Video file uploaded but content appears to be generic placeholder. Unable to verify solar platform demonstration.'
                },
                'is_consistent': False,
                'inconsistency_reasons': [
                    'CRITICAL: Uploaded image (solar_platform.png) shows a food delivery app interface, not a solar energy platform',
                    'The visual materials do not support the claims made in the written submission',
                    'Possible submission error or intentional misrepresentation',
                    'Recommend manual review by jury before scoring'
                ],
                'is_complete': True,
                'completeness_notes': '⚠️ While all required fields are filled, there is a MAJOR DISCREPANCY between the written proposal (solar energy) and the uploaded image (food delivery app). This submission requires careful jury review.'
            }
        }
        
        # Get AI summary data for this submission
        summary_data = ai_summaries.get(submission.title, {
            'summary': f'This submission presents {submission.title}, an innovative solution addressing {submission.final_category} sector challenges. The idea demonstrates creative problem-solving with a clear implementation roadmap.',
            'tags': [submission.final_category, 'technology'],
            'file_summaries': {},
            'is_consistent': True,
            'inconsistency_reasons': [],
            'is_complete': True,
            'completeness_notes': 'Submission contains all required sections.'
        })
        
        # Create AISummary record
        ai_summary = AISummary.objects.create(
            submission=submission,
            summary=summary_data['summary'],
            suggested_tags=summary_data['tags'],
            file_summaries=summary_data['file_summaries'],
            is_consistent=summary_data['is_consistent'],
            inconsistency_reasons=summary_data['inconsistency_reasons'],
            is_complete=summary_data['is_complete'],
            completeness_notes=summary_data['completeness_notes'],
            model_used='claude-3-5-sonnet-20241022',
            tokens_used=random.randint(1500, 3500),
            processing_time=round(random.uniform(2.5, 8.5), 2),
            raw_response='{"status": "success", "generated_for": "dummy_data"}'
        )
        
        self.stdout.write(f'    ✓ Added AI Summary')

