from django.urls import path
from .views import AllCaptureMachinesView, CaptureMachineSearchView

urlpatterns = [
    path('all-capture-machines/', AllCaptureMachinesView.as_view(), name='all_capture_machines'),
    path('search-capture-machine/', CaptureMachineSearchView.as_view(), name='search-capture-machine'),
]