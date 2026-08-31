import os

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (IFTxHighlight, HighlightMedia, HighlightParticipant,
                     EXT_TYPE, MAX_MB)

User = get_user_model()


def _role(user):
    return getattr(getattr(user, 'profile', None), 'role', 'student')


def is_staff_or_superuser(user):
    if user.is_staff or user.is_superuser:
        return True
    return _role(user) in ('superadmin', 'viewer')


def _school_of(user):
    return getattr(user, 'school_profile', None)


def _classify(filename):
    """Return (media_type, error_message_or_None) for an uploaded file name/size check done separately."""
    ext = os.path.splitext(filename)[1].lstrip('.').lower()
    return EXT_TYPE.get(ext), ext


def _save_media(request, highlight):
    """Validate + save each uploaded file. Returns list of error strings (empty = ok)."""
    errors = []
    for f in request.FILES.getlist('media'):
        mtype, ext = _classify(f.name)
        if not mtype:
            errors.append(f'{f.name}: unsupported file type (.{ext}).')
            continue
        limit = MAX_MB[mtype]
        if f.size > limit * 1024 * 1024:
            errors.append(f'{f.name}: {round(f.size/1048576,1)} MB exceeds the {limit} MB limit for {mtype} files.')
            continue
        HighlightMedia.objects.create(
            highlight=highlight, file=f, media_type=mtype,
            original_name=f.name, size_bytes=f.size)
    return errors


# ── School side ──────────────────────────────────────────────────────────────

@login_required
def my_highlights(request):
    school = _school_of(request.user)
    if school and school.status != 'active':
        return redirect('students:school_dashboard')
    qs = IFTxHighlight.objects.filter(created_by=request.user)
    if school:
        qs = IFTxHighlight.objects.filter(school=school)
    return render(request, 'highlights/my_highlights.html', {'highlights': qs})


@login_required
def upload_highlight(request):
    school = _school_of(request.user)
    if school and school.status != 'active':
        return redirect('students:school_dashboard')
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        event_date = request.POST.get('event_date') or None
        summary = (request.POST.get('summary') or '').strip()

        if not title or not event_date:
            messages.error(request, 'Event title and date are required.')
            return render(request, 'highlights/upload_highlight.html', {'max_mb': MAX_MB})

        highlight = IFTxHighlight.objects.create(
            school=_school_of(request.user), created_by=request.user,
            title=title, event_date=event_date, summary=summary)

        # participating students (parallel arrays from the form)
        names = request.POST.getlist('student_name')
        grades = request.POST.getlist('student_grade')
        for i, nm in enumerate(names):
            nm = (nm or '').strip()
            if nm:
                HighlightParticipant.objects.create(
                    highlight=highlight, student_name=nm,
                    grade=(grades[i].strip() if i < len(grades) else ''))

        errors = _save_media(request, highlight)
        if errors:
            for e in errors:
                messages.error(request, e)
            messages.success(request, 'Highlight saved. Some files were skipped (see messages above).')
        else:
            messages.success(request, 'IFTx Highlight uploaded successfully.')
        return redirect('students:highlight_detail', highlight_id=highlight.id)

    return render(request, 'highlights/upload_highlight.html', {'max_mb': MAX_MB})


@login_required
def highlight_detail(request, highlight_id):
    school = _school_of(request.user)
    if school and school.status != 'active':
        return redirect('students:school_dashboard')
    qs = IFTxHighlight.objects.filter(created_by=request.user)
    if school:
        qs = IFTxHighlight.objects.filter(school=school)
    highlight = get_object_or_404(qs, id=highlight_id)

    # allow adding more media to own highlight
    if request.method == 'POST':
        errors = _save_media(request, highlight)
        for e in errors:
            messages.error(request, e)
        if not errors:
            messages.success(request, 'Media added.')
        return redirect('students:highlight_detail', highlight_id=highlight.id)

    return render(request, 'highlights/highlight_detail.html', {'highlight': highlight})


# ── Admin side ───────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_staff_or_superuser)
def admin_highlights(request):
    from students.models import School

    qs = IFTxHighlight.objects.select_related('school', 'created_by').prefetch_related('media', 'participants')

    school_id = request.GET.get('school', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    media_type = request.GET.get('media', '')

    if school_id:
        qs = qs.filter(school_id=school_id)
    if date_from:
        qs = qs.filter(event_date__gte=date_from)
    if date_to:
        qs = qs.filter(event_date__lte=date_to)
    if media_type:
        qs = qs.filter(media__media_type=media_type).distinct()

    highlights = list(qs)
    total_media = sum(h.media.count() for h in highlights)

    return render(request, 'admins/highlights/list.html', {
        'highlights': highlights,
        'total_media': total_media,
        'schools': School.objects.order_by('name').values('id', 'name'),
        'school_id': school_id, 'date_from': date_from, 'date_to': date_to, 'media_type': media_type,
        'media_types': ['image', 'video', 'ppt', 'pdf', 'doc'],
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def admin_highlight_detail(request, highlight_id):
    highlight = get_object_or_404(
        IFTxHighlight.objects.select_related('school', 'created_by'), id=highlight_id)

    if request.method == 'POST' and request.POST.get('action') == 'toggle_reviewed':
        highlight.is_reviewed = not highlight.is_reviewed
        highlight.reviewed_at = timezone.now() if highlight.is_reviewed else None
        highlight.save(update_fields=['is_reviewed', 'reviewed_at', 'updated_at'])
        messages.success(request, 'Marked reviewed.' if highlight.is_reviewed else 'Marked not reviewed.')
        return redirect('admins:admin_highlight_detail', highlight_id=highlight.id)

    return render(request, 'admins/highlights/detail.html', {'highlight': highlight})


@login_required
@user_passes_test(is_staff_or_superuser)
def admin_highlights_export(request):
    """Excel 'dump' of highlights honouring the same filters as the list."""
    from admins.reports import xlsx_response

    qs = IFTxHighlight.objects.select_related('school', 'created_by').prefetch_related('media', 'participants')
    if request.GET.get('school'):
        qs = qs.filter(school_id=request.GET['school'])
    if request.GET.get('from'):
        qs = qs.filter(event_date__gte=request.GET['from'])
    if request.GET.get('to'):
        qs = qs.filter(event_date__lte=request.GET['to'])
    if request.GET.get('media'):
        qs = qs.filter(media__media_type=request.GET['media']).distinct()

    headers = ['Event Date', 'School', 'Uploaded By', 'Title', 'Summary',
               'Media Count', 'Media Types', 'Participants', 'Reviewed', 'Uploaded On']
    rows = []
    for h in qs:
        types = ', '.join(sorted({m.media_type for m in h.media.all()}))
        parts = ', '.join(f'{p.student_name}{" ("+p.grade+")" if p.grade else ""}' for p in h.participants.all())
        rows.append([
            h.event_date.strftime('%Y-%m-%d') if h.event_date else '',
            h.school_name,
            (h.created_by.get_full_name() or h.created_by.username) if h.created_by else '',
            h.title, h.summary, h.media.count(), types, parts,
            'Yes' if h.is_reviewed else 'No',
            h.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return xlsx_response('iftx_highlights', headers, rows, 'IFTx Highlights')
