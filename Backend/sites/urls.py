from django.urls import path
from .views import CreatSiteView,SiteListView ,UpdateSiteDetail

urlpatterns = [
    path('add-site/', CreatSiteView.as_view(), name='add-site'),
    path('sites/', SiteListView.as_view(), name='sites'),
    path('update-site/<int:pk>/', UpdateSiteDetail.as_view(), name='update_site'),
]
