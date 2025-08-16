from django.urls import path
from .views import CreatMachineView , DisplayMachineView

urlpatterns = [

    path('add-machine/', CreatMachineView.as_view(), name='add-machine'),
    path('machines/', DisplayMachineView.as_view(), name='machines-list'),

]
