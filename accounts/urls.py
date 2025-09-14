from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path('pricing/', views.pricing_view, name='pricing'),
    # Company pages
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('help/', views.help_center_view, name='help_center'),
    path('status/', views.status_view, name='status'),
    # Legal pages
    path('privacy/', views.privacy_view, name='privacy'),
    path('terms/', views.terms_view, name='terms'),
    # Additional SaaS pages
    path('faq/', views.faq_view, name='faq'),
    path('docs/', views.documentation_view, name='documentation'),
]