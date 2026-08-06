from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Ticket, TicketMessage, TicketAttachment, TicketEvent

User = get_user_model()


def _log(ticket, actor, verb, detail=''):
    """Record an entry in the ticket's action timeline. Never breaks a request."""
    try:
        TicketEvent.objects.create(ticket=ticket, actor=actor, verb=verb, detail=detail[:300])
    except Exception:
        pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _role(user):
    return getattr(getattr(user, 'profile', None), 'role', 'student')


def _creator_type(user):
    return 'school' if _role(user) == 'school' else 'student'


def _superadmins():
    return User.objects.filter(
        Q(is_superuser=True) | Q(is_staff=True) | Q(profile__role='superadmin')
    ).distinct()


def _notify(user, title, message, url):
    """Fire an in-app + web-push notification; never breaks the request."""
    try:
        from students.push import notify
        notify(user, 'ticket', title, message, icon='confirmation_number',
               action_url=url, action_label='View Ticket')
    except Exception:
        pass


def _email(to, subject, body, action_url=''):
    try:
        from accounts.emails import send_branded_email
        send_branded_email(subject, to, 'accounts/email_generic.html',
                           {'title': subject, 'body': body,
                            'action_url': action_url, 'button_label': 'View Ticket'})
    except Exception:
        pass


def _notify_watchers(ticket, event_label, detail=''):
    """Email a full ticket snapshot to the internal watcher addresses on every
    ticket event. Fully fail-safe — never breaks the ticket action."""
    try:
        from django.conf import settings
        from accounts.emails import send_branded_email
        recipients = getattr(settings, 'TICKET_NOTIFY_EMAILS', [])
        if not recipients:
            return
        owner = ticket.created_by
        raised_by = (owner.get_full_name() or owner.username) if owner else '—'
        raised_email = owner.email if owner else '—'
        # School name — from the student's school, or the school user's own name.
        school_name = '—'
        if owner:
            stu = getattr(owner, 'student_profile', None)
            sch = getattr(owner, 'school_profile', None)
            if stu is not None:
                school_name = getattr(stu, 'school_name', '') or (
                    getattr(getattr(stu, 'school', None), 'name', '') or '—')
            elif sch is not None:
                school_name = getattr(sch, 'name', '') or '—'
        assigned = ticket.assigned_to.get_full_name() if ticket.assigned_to else 'Not assigned'
        url = f'/super-admin/tickets/{ticket.id}/'
        lines = [
            f'Event: {event_label}',
        ]
        if detail:
            lines.append(f'Detail: {detail}')
        lines += [
            '',
            f'Ticket: {ticket.ticket_number}',
            f'Subject: {ticket.subject}',
            f'Category: {ticket.get_category_display()}',
            f'Priority: {ticket.get_priority_display()}',
            f'Status: {ticket.get_status_display()}',
            f'Raised by: {raised_by} ({raised_email}) — {ticket.get_creator_type_display()}',
            f'School: {school_name}',
            f'Assigned to: {assigned}',
            '',
            f'Problem / Description:\n{ticket.description}',
        ]
        body = '\n'.join(lines)
        subject = f'[{ticket.ticket_number}] {event_label} — {ticket.subject}'
        send_branded_email(subject, recipients, 'accounts/email_generic.html',
                           {'title': subject, 'body': body,
                            'action_url': url, 'button_label': 'View Ticket'})
    except Exception:
        pass


def _save_attachment(request, ticket, message=None):
    f = request.FILES.get('attachment')
    if f:
        TicketAttachment.objects.create(
            ticket=ticket, message=message, file=f,
            original_name=f.name, uploaded_by=request.user)


def is_staff_or_superuser(user):
    if user.is_staff or user.is_superuser:
        return True
    return _role(user) in ('superadmin', 'viewer')


# ── user side (student + school) ─────────────────────────────────────────────

@login_required
def my_tickets(request):
    tickets = Ticket.objects.filter(created_by=request.user)
    return render(request, 'support/my_tickets.html', {'tickets': tickets})


@login_required
def raise_ticket(request):
    if request.method == 'POST':
        subject = (request.POST.get('subject') or '').strip()
        category = request.POST.get('category') or 'other'
        priority = request.POST.get('priority') or 'medium'
        description = (request.POST.get('description') or '').strip()

        if not subject or not description:
            messages.error(request, 'Subject and description are required.')
        else:
            ticket = Ticket.objects.create(
                created_by=request.user,
                creator_type=_creator_type(request.user),
                subject=subject, category=category, priority=priority,
                description=description, status='open',
            )
            _save_attachment(request, ticket)
            _log(ticket, request.user, 'created', subject)
            _notify_watchers(ticket, 'New ticket raised', subject)
            url = f'/super-admin/tickets/{ticket.id}/'
            for admin in _superadmins():
                _notify(admin, f'New ticket {ticket.ticket_number}',
                        f'{subject}', url)
            messages.success(
                request,
                'Your ticket has been created successfully. Our support team '
                'will respond within 48 Working Hours.')
            return redirect('students:ticket_detail', ticket_id=ticket.id)

    return render(request, 'support/raise_ticket.html', {
        'categories': Ticket.CATEGORY_CHOICES,
        'priorities': Ticket.PRIORITY_CHOICES,
    })


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)

    if request.method == 'POST':
        action = request.POST.get('action', 'reply')
        if action == 'reopen' and ticket.can_reopen:
            ticket.status = 'reopened'
            ticket.save(update_fields=['status', 'updated_at'])
            _log(ticket, request.user, 'reopened')
            _notify_watchers(ticket, 'Reopened by user')
            target = ticket.assigned_to
            url = f'/super-admin/tickets/{ticket.id}/'
            for admin in ([target] if target else _superadmins()):
                if admin:
                    _notify(admin, f'Ticket {ticket.ticket_number} reopened',
                            ticket.subject, url)
            messages.success(request, 'Ticket reopened. Our team will look into it again.')
        else:
            body = (request.POST.get('body') or '').strip()
            if body:
                msg = TicketMessage.objects.create(
                    ticket=ticket, author=request.user, body=body)
                _save_attachment(request, ticket, message=msg)
                _log(ticket, request.user, 'replied', body[:120])
                _notify_watchers(ticket, 'New reply from user', body)
                # user replied → move an admin-side state back into the queue
                if ticket.status in ('resolved', 'waiting_user'):
                    ticket.status = 'reopened' if ticket.status == 'resolved' else 'in_progress'
                ticket.save(update_fields=['status', 'updated_at'])
                url = f'/super-admin/tickets/{ticket.id}/'
                for admin in ([ticket.assigned_to] if ticket.assigned_to else _superadmins()):
                    if admin:
                        _notify(admin, f'Reply on {ticket.ticket_number}', body[:80], url)
                messages.success(request, 'Reply sent.')
        return redirect('students:ticket_detail', ticket_id=ticket.id)

    return render(request, 'support/ticket_detail.html', {
        'ticket': ticket,
        'messages_thread': ticket.messages.filter(is_internal=False).select_related('author'),
    })


# ── admin side ───────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_staff_or_superuser)
def admin_tickets(request):
    tab = request.GET.get('tab', 'student')
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')

    base = Ticket.objects.select_related('created_by', 'assigned_to').filter(merged_into__isnull=True)
    overdue_count = sum(1 for t in base if t.is_overdue)
    counts = {
        'total': base.count(),
        'student': base.filter(creator_type='student').count(),
        'school': base.filter(creator_type='school').count(),
        'open': base.filter(status='open').count(),
        'in_progress': base.filter(status='in_progress').count(),
        'resolved': base.filter(status='resolved').count(),
        'closed': base.filter(status='closed').count(),
        'overdue': overdue_count,
    }

    tickets = base.filter(creator_type=('school' if tab == 'school' else 'student'))
    if status:
        tickets = tickets.filter(status=status)
    if priority:
        tickets = tickets.filter(priority=priority)
    tickets = list(tickets)
    if request.GET.get('overdue') == '1':
        tickets = [t for t in tickets if t.is_overdue]

    return render(request, 'admins/tickets/list.html', {
        'counts': counts, 'tickets': tickets, 'tab': tab,
        'status': status, 'priority': priority,
        'overdue_only': request.GET.get('overdue') == '1',
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def admin_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(
        Ticket.objects.select_related('created_by', 'assigned_to'), id=ticket_id)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        url = f'/help/ticket/{ticket.id}/'
        owner = ticket.created_by

        if action == 'reply':
            body = (request.POST.get('body') or '').strip()
            if body:
                msg = TicketMessage.objects.create(ticket=ticket, author=request.user, body=body)
                _save_attachment(request, ticket, message=msg)
                if ticket.status in ('open', 'reopened'):
                    ticket.status = 'in_progress'
                ticket.save(update_fields=['status', 'updated_at'])
                _log(ticket, request.user, 'replied', body[:120])
                _notify(owner, f'Reply on {ticket.ticket_number}', body[:80], url)
                _email(owner.email, f'Reply on your ticket {ticket.ticket_number}', body, url)
                _notify_watchers(ticket, 'Support replied', body)
                messages.success(request, 'Reply sent to user.')

        elif action == 'note':
            body = (request.POST.get('body') or '').strip()
            if body:
                TicketMessage.objects.create(
                    ticket=ticket, author=request.user, body=body, is_internal=True)
                _log(ticket, request.user, 'note', body[:120])
                _notify_watchers(ticket, 'Internal note added', body)
                messages.success(request, 'Internal note added (not visible to the user).')

        elif action == 'status':
            new_status = request.POST.get('status')
            if new_status in dict(Ticket.STATUS_CHOICES):
                ticket.status = new_status
                ticket.save(update_fields=['status', 'updated_at'])
                _log(ticket, request.user, 'status', ticket.get_status_display())
                _notify(owner, f'Ticket {ticket.ticket_number} updated',
                        f'Status: {ticket.get_status_display()}', url)
                _notify_watchers(ticket, f'Status changed to {ticket.get_status_display()}')
                messages.success(request, 'Status updated.')

        elif action == 'priority':
            new_priority = request.POST.get('priority')
            if new_priority in dict(Ticket.PRIORITY_CHOICES):
                ticket.priority = new_priority
                ticket.save(update_fields=['priority', 'updated_at'])
                _log(ticket, request.user, 'priority', ticket.get_priority_display())
                _notify_watchers(ticket, f'Priority changed to {ticket.get_priority_display()}')
                messages.success(request, 'Priority updated.')

        elif action == 'assign':
            assignee_id = request.POST.get('assigned_to')
            if assignee_id:
                ticket.assigned_to = User.objects.filter(id=assignee_id).first()
            else:
                ticket.assigned_to = None
            if ticket.status == 'open':
                ticket.status = 'in_progress'
            ticket.save(update_fields=['assigned_to', 'status', 'updated_at'])
            _assignee_label = ticket.assigned_to.get_full_name() if ticket.assigned_to else 'Unassigned'
            _log(ticket, request.user, 'assigned', _assignee_label)
            _notify_watchers(ticket, f'Assigned to {_assignee_label}')
            messages.success(request, 'Ticket assigned.')

        elif action == 'resolve':
            note = (request.POST.get('resolution_note') or '').strip()
            ticket.status = 'resolved'
            ticket.resolution_note = note
            ticket.resolved_at = timezone.now()
            ticket.save(update_fields=['status', 'resolution_note', 'resolved_at', 'updated_at'])
            _log(ticket, request.user, 'resolved', note[:120])
            _notify(owner, f'Ticket {ticket.ticket_number} resolved',
                    note[:80] or 'Your issue has been resolved.', url)
            _email(owner.email, f'Your ticket {ticket.ticket_number} has been resolved',
                   note or 'Our team has resolved your issue. If you are still facing '
                   'the problem, you can reopen the ticket from your dashboard.', url)
            _notify_watchers(ticket, 'Resolved', note)
            messages.success(request, 'Ticket marked as resolved. User notified.')

        elif action == 'reopen':
            ticket.status = 'reopened'
            ticket.save(update_fields=['status', 'updated_at'])
            _log(ticket, request.user, 'reopened')
            _notify(owner, f'Ticket {ticket.ticket_number} reopened', ticket.subject, url)
            _notify_watchers(ticket, 'Reopened by admin')
            messages.success(request, 'Ticket reopened.')

        elif action == 'merge':
            target_id = request.POST.get('merge_into')
            target = Ticket.objects.filter(id=target_id).exclude(id=ticket.id).first()
            if target:
                # Move this ticket's conversation + attachments onto the target.
                ticket.messages.update(ticket=target)
                ticket.attachments.update(ticket=target)
                ticket.merged_into = target
                ticket.status = 'closed'
                ticket.save(update_fields=['merged_into', 'status', 'updated_at'])
                _log(target, request.user, 'merged', f'{ticket.ticket_number} merged in')
                _log(ticket, request.user, 'merged', f'Merged into {target.ticket_number}')
                _notify_watchers(ticket, f'Merged into {target.ticket_number}')
                messages.success(request, f'Ticket merged into {target.ticket_number}.')
                return redirect('admins:admin_ticket_detail', ticket_id=target.id)
            messages.error(request, 'Select a valid ticket to merge into.')

        elif action == 'delete':
            num = ticket.ticket_number
            ticket.delete()
            messages.success(request, f'Ticket {num} deleted.')
            return redirect('admins:admin_tickets')

        return redirect('admins:admin_ticket_detail', ticket_id=ticket.id)

    # Candidate tickets to merge INTO: same creator, not already merged, not this one.
    merge_candidates = Ticket.objects.filter(
        created_by=ticket.created_by, merged_into__isnull=True
    ).exclude(id=ticket.id).order_by('-created_at')[:50]

    return render(request, 'admins/tickets/detail.html', {
        'ticket': ticket,
        'messages_thread': ticket.messages.select_related('author'),
        'events': ticket.events.select_related('actor'),
        'merge_candidates': merge_candidates,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'assignees': _superadmins().order_by('first_name'),
    })
