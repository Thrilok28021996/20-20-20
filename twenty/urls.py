from django.urls import path

from twenty import views

urlpatterns = [path("", views.index, name="index")]
