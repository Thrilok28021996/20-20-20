from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import UserCalendarConnection
import logging

logger = logging.getLogger(__name__)


@login_required
def calendar_settings_view(request):
    """Manual calendar/schedule settings for smart break timing"""
    connection, created = UserCalendarConnection.objects.get_or_create(
        user=request.user,
        defaults={
            'is_active': True,
            'check_busy_periods': True,
            'respect_focus_time': True,
            'minimum_meeting_gap_minutes': 5,
            'interruption_rule': 'between_meetings'
        }
    )

    if request.method == 'POST':
        # Update settings
        connection.is_active = request.POST.get('is_active') == 'on'
        connection.check_busy_periods = request.POST.get('check_busy_periods') == 'on'
        connection.respect_focus_time = request.POST.get('respect_focus_time') == 'on'

        interruption_rule = request.POST.get('interruption_rule')
        if interruption_rule in dict(UserCalendarConnection.INTERRUPTION_RULES):
            connection.interruption_rule = interruption_rule

        meeting_gap = request.POST.get('minimum_meeting_gap_minutes')
        if meeting_gap:
            connection.minimum_meeting_gap_minutes = int(meeting_gap)

        connection.save()
        messages.success(request, 'Break timing preferences updated successfully!')
        return redirect('calendars:settings')

    context = {
        'connection': connection,
        'interruption_rules': UserCalendarConnection.INTERRUPTION_RULES,
    }
    return render(request, 'calendars/settings.html', context)