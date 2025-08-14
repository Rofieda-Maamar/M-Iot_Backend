from django.urls import path
from .views import CreatSiteView,SiteListView

urlpatterns = [
    path('add-site/', CreatSiteView.as_view(), name='add-site'),
    path('sites/', SiteListView.as_view(), name='sites'),


]
