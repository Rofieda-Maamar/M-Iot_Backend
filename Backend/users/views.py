from django.shortcuts import render
from .Serializers import UserSerializer 
from rest_framework import generics
from .models import User
# Create your views here.

class AddUserView(generics.CreateAPIView) :  # creatApiView hendle : post , call the serializer , validat the data , calls .creat, and return the response
    queryset= User.objects.all()
    serializer_class=UserSerializer