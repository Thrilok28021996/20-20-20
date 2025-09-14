from django.urls import path
from . import views

app_name = 'timer'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('real-time/', views.real_time_dashboard_view, name='real_time_dashboard'),
    path('start/', views.start_session_view, name='start_session'),
    path('end/', views.end_session_view, name='end_session'),
    path('sync/', views.sync_session_view, name='sync_session'),
    path('break/', views.take_break_view, name='take_break'),
    path('complete-break/', views.complete_break_view, name='complete_break'),
    path('settings/', views.timer_settings_view, name='settings'),
    path('update-dark-mode/', views.update_dark_mode_view, name='update_dark_mode'),
    path('statistics/', views.statistics_view, name='statistics'),
]