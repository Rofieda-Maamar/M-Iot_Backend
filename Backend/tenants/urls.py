# tenants/urls.py

from django.urls import path
from .views import AddClientView

urlpatterns = [
    path('add-client/', AddClientView.as_view(), name='add-client'),
]
