from django.urls import path
from .views import AddMaintenanceAdminView, AddMaintenanceClientView, AllMaintenanceAdminView, AllMaintenanceClientView, MaintenanceAdminDetailView, MaintenanceClientDetailView, SearchMaintenanceAdminView

urlpatterns = [
    path('add-maintenance-admin/', AddMaintenanceAdminView.as_view(), name='add-maintenance-admin'),
    path('all-maintenances/', AllMaintenanceAdminView.as_view(), name='all-maintenances'),
    path('search/', SearchMaintenanceAdminView.as_view(), name='search-maintenances'),
    path('detail/<str:capteur_num_serie>/<int:maintenance_id>/', MaintenanceAdminDetailView.as_view(), name='maintenance-detail'),


 
    # Client maintenance URLs
    path('add-maintenance-client/', AddMaintenanceClientView.as_view(), name='add-maintenance-client'),
    path('all-maintenance-client/', AllMaintenanceClientView.as_view(), name='all-maintenance-client'),
    path('detail-client/<str:machine_identificateur>/<int:maintenance_id>/', MaintenanceClientDetailView.as_view(), name='maintenance-client-detail'),
   

]
