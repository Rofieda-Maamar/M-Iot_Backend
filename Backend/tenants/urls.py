# tenants/urls.py

from django.urls import path
from .views import AddClientView , ClientListView  , ClientDetailView

urlpatterns = [
    path('add-client/', AddClientView.as_view(), name='add-client'),
    path('clients/', ClientListView.as_view() , name='list-clients') ,
    path('clients/<int:pk>/' , ClientDetailView.as_view() , name = 'client-detail'),
]
