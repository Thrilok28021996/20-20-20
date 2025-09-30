from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from .models import Notification, NotificationPreference, BreakReminder
from django.core.paginator import Paginator


@login_required
def notification_list_view(request):
    """Display list of user notifications"""
    filter_type = request.GET.get('type', 'all')

    notifications = Notification.objects.filter(user=request.user)

    if filter_type == 'unread':
        notifications = notifications.exclude(status='read')
    elif filter_type == 'read':
        notifications = notifications.filter(status='read')
    elif filter_type != 'all':
        notifications = notifications.filter(notification_type=filter_type)

    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Unread count
    unread_count = Notification.objects.filter(
        user=request.user
    ).exclude(status='read').count()

    context = {
        'notifications': page_obj,
        'unread_count': unread_count,
        'filter_type': filter_type,
    }
    return render(request, 'notifications/notification_list.html', context)


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    notification.mark_as_read()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': 'Notification marked as read'
        })

    return redirect('notifications:list')


@login_required
@require_POST
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(
        user=request.user
    ).exclude(status='read').update(
        status='read',
        read_at=timezone.now()
    )

    messages.success(request, 'All notifications marked as read')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': 'All notifications marked as read'
        })

    return redirect('notifications:list')


@login_required
@require_POST
def delete_notification(request, notification_id):
    """Delete a specific notification"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    notification.delete()

    messages.success(request, 'Notification deleted')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': 'Notification deleted'
        })

    return redirect('notifications:list')


@login_required
def notification_preferences_view(request):
    """Manage notification preferences"""
    preferences, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )

    if request.method == 'POST':
        # Update channel preferences
        preferences.email_enabled = request.POST.get('email_enabled') == 'on'
        preferences.in_app_enabled = request.POST.get('in_app_enabled') == 'on'
        preferences.browser_push_enabled = request.POST.get('browser_push_enabled') == 'on'
        preferences.desktop_enabled = request.POST.get('desktop_enabled') == 'on'

        # Update notification type preferences
        preferences.break_reminders = request.POST.get('break_reminders') == 'on'
        preferences.daily_summaries = request.POST.get('daily_summaries') == 'on'
        preferences.weekly_reports = request.POST.get('weekly_reports') == 'on'
        preferences.streak_milestones = request.POST.get('streak_milestones') == 'on'
        preferences.tips_and_advice = request.POST.get('tips_and_advice') == 'on'
        preferences.promotional_emails = request.POST.get('promotional_emails') == 'on'

        # Update timing preferences
        preferences.weekend_notifications = request.POST.get('weekend_notifications') == 'on'

        quiet_start = request.POST.get('quiet_hours_start')
        quiet_end = request.POST.get('quiet_hours_end')
        preferences.quiet_hours_start = quiet_start if quiet_start else None
        preferences.quiet_hours_end = quiet_end if quiet_end else None

        # Break reminder settings
        advance_seconds = request.POST.get('break_reminder_advance_seconds')
        if advance_seconds:
            preferences.break_reminder_advance_seconds = int(advance_seconds)

        max_snooze = request.POST.get('max_snooze_count')
        if max_snooze:
            preferences.max_snooze_count = int(max_snooze)

        snooze_duration = request.POST.get('snooze_duration_minutes')
        if snooze_duration:
            preferences.snooze_duration_minutes = int(snooze_duration)

        preferences.save()
        messages.success(request, 'Notification preferences updated successfully!')
        return redirect('notifications:preferences')

    context = {
        'preferences': preferences,
    }
    return render(request, 'notifications/preferences.html', context)


@login_required
def get_unread_count(request):
    """API endpoint to get unread notification count"""
    count = Notification.objects.filter(
        user=request.user
    ).exclude(status='read').count()

    return JsonResponse({
        'unread_count': count
    })


@login_required
def get_recent_notifications(request):
    """API endpoint to get recent notifications"""
    limit = int(request.GET.get('limit', 5))

    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:limit]

    notifications_data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.notification_type,
        'status': n.status,
        'created_at': n.created_at.isoformat(),
        'action_url': n.action_url,
    } for n in notifications]

    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': Notification.objects.filter(
            user=request.user
        ).exclude(status='read').count()
    })


@login_required
@require_POST
def snooze_break_reminder(request, reminder_id):
    """Snooze a break reminder"""
    reminder = get_object_or_404(
        BreakReminder,
        id=reminder_id,
        user=request.user
    )

    preferences = NotificationPreference.objects.get_or_create(user=request.user)[0]

    if reminder.snooze_count >= preferences.max_snooze_count:
        return JsonResponse({
            'status': 'error',
            'message': f'Maximum snooze count ({preferences.max_snooze_count}) reached'
        }, status=400)

    reminder.snooze_reminder(minutes=preferences.snooze_duration_minutes)

    return JsonResponse({
        'status': 'success',
        'message': f'Reminder snoozed for {preferences.snooze_duration_minutes} minutes',
        'snooze_until': reminder.snooze_until.isoformat()
    })


@login_required
@require_POST
def dismiss_break_reminder(request, reminder_id):
    """Dismiss a break reminder"""
    reminder = get_object_or_404(
        BreakReminder,
        id=reminder_id,
        user=request.user
    )

    reminder.user_response = 'dismissed'
    reminder.response_time = timezone.now()
    reminder.save()

    # Mark associated notification as read
    if hasattr(reminder, 'notification'):
        reminder.notification.mark_as_read()

    return JsonResponse({
        'status': 'success',
        'message': 'Reminder dismissed'
    })