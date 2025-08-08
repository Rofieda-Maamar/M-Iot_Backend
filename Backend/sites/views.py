from django.shortcuts import render
from rest_framework import generics
from .serializers import SiteSerializer
# Create your views here.


class CreatSiteView (generics.CreateAPIView) : 
    serializer_class = SiteSerializer