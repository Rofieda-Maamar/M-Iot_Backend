from django.urls import path
from .views import AddMaintenanceAdminView, AllMaintenanceAdminView, MaintenanceAdminDetailView, SearchMaintenanceAdminView

urlpatterns = [
    path('add-maintenance-admin/', AddMaintenanceAdminView.as_view(), name='add-maintenance-admin'),
    path('all-maintenances/', AllMaintenanceAdminView.as_view(), name='all-maintenances'),
    path('search/', SearchMaintenanceAdminView.as_view(), name='search-maintenances'),
    path('detail/<str:capteur_num_serie>/<int:maintenance_id>/', MaintenanceAdminDetailView.as_view(), name='maintenance-detail'),
]
