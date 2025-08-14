from django.urls import path
from .views import CreatMachineView

urlpatterns = [

    path('add-machine/', CreatMachineView.as_view(), name='add-machine'),
]
