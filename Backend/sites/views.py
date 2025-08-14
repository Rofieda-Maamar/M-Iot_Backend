from django.shortcuts import render
from rest_framework import generics
from .models import Site
from .serializers import SiteSerializer , SiteDisplaySerializer
# Create your views here.


class CreatSiteView (generics.CreateAPIView) : 
    serializer_class = SiteSerializer


class SiteListView(generics.ListAPIView) : 
    queryset = Site.objects.all()
    serializer_class = SiteDisplaySerializer