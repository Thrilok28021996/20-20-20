from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Notification list and management
    path('', views.notification_list_view, name='list'),
    path('preferences/', views.notification_preferences_view, name='preferences'),
    path('<int:notification_id>/read/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('<int:notification_id>/delete/', views.delete_notification, name='delete'),

    # API endpoints
    path('api/unread-count/', views.get_unread_count, name='unread_count_api'),
    path('api/recent/', views.get_recent_notifications, name='recent_api'),

    # Break reminders
    path('break-reminder/<int:reminder_id>/snooze/', views.snooze_break_reminder, name='snooze_reminder'),
    path('break-reminder/<int:reminder_id>/dismiss/', views.dismiss_break_reminder, name='dismiss_reminder'),
]