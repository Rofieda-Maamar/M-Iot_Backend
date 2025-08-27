from django.urls import path
from .views import  *

urlpatterns = [

    path('add-machine/', CreatMachineView.as_view(), name='add-machine'),
    path('upload-machine/', MachineUploadView.as_view(), name='upload-machine'),
    path('machines/', DisplayMachineView.as_view(), name='machines-list'),
    path('all-capture-machines/', AllCaptureMachinesView.as_view(), name='all_capture_machines'),
    path('search-capture-machine/', CaptureMachineSearchView.as_view(), name='search-capture-machine'),
    path('machine-detail/', DisplayMachineDetailView.as_view(), name='search-capture-machine'),
    path('machine-dashboard/<int:pk>/', MachineDashboardView.as_view(), name='machine-dashboard'),
    path('machine/last-values/<int:machine_id>/', MachineCapturesLastValuesSSEView, name='machine-last-captures'),
    path('machine/sse-param/<int:machine_id>/', machine_params_sse, name='machine-last-captures'),

]
