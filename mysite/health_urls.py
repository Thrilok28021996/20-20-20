"""
Health check and monitoring URLs.
"""
from django.urls import path
from .health_check import (
    health_check,
    detailed_health_check,
    readiness_check,
    liveness_check
)

app_name = 'health'

urlpatterns = [
    path('', health_check, name='health'),
    path('detailed/', detailed_health_check, name='detailed'),
    path('ready/', readiness_check, name='ready'),
    path('live/', liveness_check, name='live'),
]
