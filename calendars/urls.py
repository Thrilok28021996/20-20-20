from django.urls import path
from . import views

app_name = 'calendars'

urlpatterns = [
    # Manual schedule settings (no API required)
    path('settings/', views.calendar_settings_view, name='settings'),
]