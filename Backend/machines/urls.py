from django.urls import path
from .views import CreatMachineView , DisplayMachineView 
from .views import  AllCaptureMachinesView, CaptureMachineSearchView

urlpatterns = [

    path('add-machine/', CreatMachineView.as_view(), name='add-machine'),
    path('machines/', DisplayMachineView.as_view(), name='machines-list'),
    path('all-capture-machines/', AllCaptureMachinesView.as_view(), name='all_capture_machines'),
    path('search-capture-machine/', CaptureMachineSearchView.as_view(), name='search-capture-machine'),

]
