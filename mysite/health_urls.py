"""
Health monitoring and system status URL configuration.
"""
from django.urls import path
from . import health_views

app_name = 'health'

urlpatterns = [
    path('', health_views.health_check_view, name='health_check'),
    path('detailed/', health_views.detailed_health_view, name='detailed_health'),
    path('errors/', health_views.error_metrics_view, name='error_metrics'),
    path('performance/', health_views.performance_metrics_view, name='performance_metrics'),
    path('status/', health_views.system_status_view, name='system_status'),
]