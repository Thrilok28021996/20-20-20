"""
URL configuration for EyeHealth 20-20-20 SaaS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Admin site customization
admin.site.site_header = "EyeHealth 20-20-20 Administration"
admin.site.site_title = "EyeHealth 20-20-20 Admin"
admin.site.index_title = "Welcome to EyeHealth 20-20-20 Administration"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('timer/', include('timer.urls')),
    path('analytics/', include('analytics.urls')),
    path('notifications/', include('notifications.urls')),
    path('subscriptions/', include('subscriptions.urls')),
    path('payments/', include('payments.urls')),
]

# Serve media and static files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Django automatically serves static files from STATICFILES_DIRS when DEBUG=True
    # But let's add explicit static serving to be sure
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
