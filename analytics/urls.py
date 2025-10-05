from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Real-time API endpoints
    path('api/real-time-metrics/', views.real_time_metrics_api, name='real_time_metrics_api'),
    path('api/dashboard-metrics/', views.user_dashboard_metrics_api, name='dashboard_metrics_api'),
    path('api/track-activity/', views.track_user_activity, name='track_activity'),
    path('api/submit-rating/', views.submit_satisfaction_rating, name='submit_rating'),
    path('api/live-feed/', views.live_activity_feed_api, name='live_feed_api'),
    path('track-conversion/', views.track_conversion, name='track_conversion'),

    # Admin dashboard
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
]