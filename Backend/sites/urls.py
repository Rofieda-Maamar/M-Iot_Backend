from django.urls import path
from .views import *

urlpatterns = [
    path('add-site/', CreatSiteView.as_view(), name='add-site'),
    path('sites/', SiteListView.as_view(), name='sites'), 
    path('site-position/<int:pk>/', SitePositionView.as_view(), name='sites'), 
    path('update-site/<int:pk>/', UpdateSiteDetail.as_view(), name='update_site'),
    path('captures-site/<int:pk>/', SiteCapturesDisplayView.as_view(), name='update_site'),
    path('upload-sites/', SiteUploadView.as_view(), name='update_site'),

]
