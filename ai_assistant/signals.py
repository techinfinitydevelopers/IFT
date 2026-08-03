"""Fires the Top 12 / Zonal Pitch Fest emails the moment an admin flips the
corresponding flag on AIEvaluation to True in Django admin.

There is no scoring formula for either stage — Top 12 (national finale) and
Zonal Pitch Fest invites are jury/admin selections — so a human still has to
set the flag. Everything AFTER that decision (the send itself) is automatic
and exactly-once (dedup via MilestoneEmailLog), which is the closest to
"fully automatic" these two stages can get without inventing a fake formula.
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import AIEvaluation

_FLAG_TO_MILESTONE = {
    'is_top_12': 'top12',
    'zonal_pitch_invited': 'zonal_pitch',
}


@receiver(pre_save, sender=AIEvaluation)
def _stash_previous_flags(sender, instance, **kwargs):
    """Remember the DB's current flag values so post_save can tell False->True
    transitions apart from an unrelated save (e.g. re-scoring) where the flag
    was already True."""
    if not instance.pk:
        instance._prev_milestone_flags = {}
        return
    prev = (AIEvaluation.objects.filter(pk=instance.pk)
            .values(*_FLAG_TO_MILESTONE.keys()).first())
    instance._prev_milestone_flags = prev or {}


@receiver(post_save, sender=AIEvaluation)
def _send_manual_milestone_emails(sender, instance, created, **kwargs):
    from students.milestone_emails import send_milestone_email

    prev = getattr(instance, '_prev_milestone_flags', {})
    for field, milestone in _FLAG_TO_MILESTONE.items():
        was_true = bool(prev.get(field))
        is_true = bool(getattr(instance, field))
        if is_true and not was_true:
            send_milestone_email(instance.submission.student, milestone)
            if field == 'is_top_12':
                # Hall of Fame / Pitch Ticket announces the same event (2-day
                # Bootcamp + Grand Finale) — send it alongside the Top 12 email.
                send_milestone_email(instance.submission.student, 'hall_of_fame')
