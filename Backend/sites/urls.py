from django.urls import path
from .views import CreatSiteView
urlpatterns = [
    path('add-site/', CreatSiteView.as_view(), name='add-site'),

]
