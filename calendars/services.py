"""
Calendar integration services for smart interruption management
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CalendarServiceBase(ABC):
    """
    Abstract base class for calendar service implementations
    """

    def __init__(self, connection):
        self.connection = connection
        self.provider = connection.provider

    @abstractmethod
    def authenticate(self, auth_code=None):
        """Authenticate with the calendar provider"""
        pass

    @abstractmethod
    def refresh_token(self):
        """Refresh the access token"""
        pass

    @abstractmethod
    def get_events(self, start_time, end_time):
        """Get calendar events for the specified time range"""
        pass

    @abstractmethod
    def get_free_busy_info(self, start_time, end_time):
        """Get free/busy information for the specified time range"""
        pass

    def is_user_busy(self, check_time):
        """
        Check if user is busy at a specific time
        Returns (is_busy, blocking_events, next_free_slot)
        """
        # Check 30 minutes around the check time
        start_time = check_time - timedelta(minutes=15)
        end_time = check_time + timedelta(minutes=45)

        try:
            events = self.get_events(start_time, end_time)
            blocking_events = []

            for event in events:
                if event.should_block_interruption(self.connection.interruption_rule):
                    if event.start_time <= check_time <= event.end_time:
                        blocking_events.append(event)

            is_busy = len(blocking_events) > 0

            # Find next free slot if currently busy
            next_free_slot = None
            if is_busy:
                next_free_slot = self._find_next_free_slot(check_time, end_time)

            return is_busy, blocking_events, next_free_slot

        except Exception as e:
            logger.error(f"Error checking busy status: {e}")
            # Default to not busy if we can't check
            return False, [], None

    def _find_next_free_slot(self, start_time, max_end_time):
        """Find the next available free slot"""
        try:
            events = self.get_events(start_time, max_end_time)

            # Sort events by start time
            events = sorted(events, key=lambda e: e.start_time)

            current_time = start_time
            for event in events:
                if event.should_block_interruption(self.connection.interruption_rule):
                    if event.start_time > current_time:
                        # Found a gap before this event
                        return current_time
                    current_time = max(current_time, event.end_time)

            # No blocking events found, can interrupt now
            return current_time if current_time > start_time else start_time

        except Exception as e:
            logger.error(f"Error finding next free slot: {e}")
            return start_time + timedelta(minutes=30)  # Default fallback


class GoogleCalendarService(CalendarServiceBase):
    """
    Google Calendar integration service
    """

    def __init__(self, connection):
        super().__init__(connection)
        self.service = None

    def authenticate(self, auth_code=None):
        """Authenticate with Google Calendar API"""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from google_auth_oauthlib.flow import Flow

            if auth_code:
                # Initial authentication with auth code
                flow = Flow.from_client_config(
                    settings.GOOGLE_CALENDAR_CONFIG,
                    scopes=['https://www.googleapis.com/auth/calendar.readonly']
                )
                flow.redirect_uri = settings.GOOGLE_CALENDAR_REDIRECT_URI

                flow.fetch_token(code=auth_code)
                credentials = flow.credentials

                # Save tokens
                self.connection.access_token = credentials.token
                self.connection.refresh_token = credentials.refresh_token
                self.connection.token_expires_at = credentials.expiry
                self.connection.save()

            else:
                # Use existing tokens
                credentials = Credentials(
                    token=self.connection.access_token,
                    refresh_token=self.connection.refresh_token,
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=settings.GOOGLE_CALENDAR_CONFIG['client_id'],
                    client_secret=settings.GOOGLE_CALENDAR_CONFIG['client_secret']
                )

            self.service = build('calendar', 'v3', credentials=credentials)
            return True

        except Exception as e:
            logger.error(f"Google Calendar authentication error: {e}")
            return False

    def refresh_token(self):
        """Refresh Google Calendar access token"""
        try:
            from google.oauth2.credentials import Credentials

            credentials = Credentials(
                token=self.connection.access_token,
                refresh_token=self.connection.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=settings.GOOGLE_CALENDAR_CONFIG['client_id'],
                client_secret=settings.GOOGLE_CALENDAR_CONFIG['client_secret']
            )

            credentials.refresh()

            # Update stored tokens
            self.connection.access_token = credentials.token
            self.connection.token_expires_at = credentials.expiry
            self.connection.save()

            return True

        except Exception as e:
            logger.error(f"Google Calendar token refresh error: {e}")
            return False

    def get_events(self, start_time, end_time):
        """Get Google Calendar events"""
        if not self.service:
            if not self.authenticate():
                return []

        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Convert to our CalendarEvent models
            calendar_events = []
            for event in events:
                # Create or update calendar event
                # This would be implemented with proper model creation
                pass

            return calendar_events

        except Exception as e:
            logger.error(f"Error fetching Google Calendar events: {e}")
            return []

    def get_free_busy_info(self, start_time, end_time):
        """Get free/busy information from Google Calendar"""
        if not self.service:
            if not self.authenticate():
                return []

        try:
            body = {
                'timeMin': start_time.isoformat(),
                'timeMax': end_time.isoformat(),
                'items': [{'id': 'primary'}]
            }

            freebusy_result = self.service.freebusy().query(body=body).execute()
            busy_periods = freebusy_result.get('calendars', {}).get('primary', {}).get('busy', [])

            return busy_periods

        except Exception as e:
            logger.error(f"Error fetching Google Calendar free/busy: {e}")
            return []


class SmartInterruptionManager:
    """
    Manages smart interruption logic based on calendar data
    """

    def __init__(self, user):
        self.user = user
        self.connections = user.calendar_connections.filter(is_active=True)

    def should_allow_interruption(self, scheduled_time):
        """
        Determine if a timer interruption should be allowed at the scheduled time
        Returns: (allowed, delay_until, reason)
        """
        if not self.connections.exists():
            # No calendar connections, allow interruption
            return True, None, "No calendar connections configured"

        all_busy = True
        earliest_free_slot = None
        blocking_reasons = []

        for connection in self.connections:
            service = self._get_service_for_connection(connection)
            if service:
                is_busy, blocking_events, next_free_slot = service.is_user_busy(scheduled_time)

                if not is_busy:
                    all_busy = False
                    break
                else:
                    blocking_reasons.extend([f"{event.title} ({event.start_time}-{event.end_time})" for event in blocking_events])
                    if next_free_slot:
                        if not earliest_free_slot or next_free_slot < earliest_free_slot:
                            earliest_free_slot = next_free_slot

        if not all_busy:
            return True, None, "User is available"

        # User is busy, determine delay strategy
        if earliest_free_slot and earliest_free_slot <= scheduled_time + timedelta(hours=1):
            return False, earliest_free_slot, f"Busy until {earliest_free_slot}: {', '.join(blocking_reasons[:2])}"
        else:
            # Too long to wait, skip this interruption
            return False, None, f"Extended busy period: {', '.join(blocking_reasons[:2])}"

    def _get_service_for_connection(self, connection):
        """Get the appropriate service instance for a calendar connection"""
        if connection.provider.name == 'google':
            return GoogleCalendarService(connection)
        elif connection.provider.name == 'outlook':
            # Would implement OutlookCalendarService
            return None
        elif connection.provider.name == 'apple':
            # Would implement AppleCalendarService
            return None
        elif connection.provider.name == 'exchange':
            # Would implement ExchangeCalendarService
            return None
        else:
            return None

    def log_interruption_decision(self, session_id, scheduled_time, decision, context=None):
        """Log the interruption decision for analytics"""
        from .models import SmartInterruptionLog

        log_entry = SmartInterruptionLog.objects.create(
            user=self.user,
            timer_session_id=session_id,
            scheduled_interruption_time=scheduled_time,
            decision=decision,
            context_data=context or {}
        )

        return log_entry