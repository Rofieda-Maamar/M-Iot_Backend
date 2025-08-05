from django.shortcuts import render
from .Serializers import UserSerializer 
from rest_framework import generics
from .models import User
from django.utils.http import urlsafe_base64_decode
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator

# Create your views here.

class AddUserView(generics.CreateAPIView) :  # creatApiView hendle : post , call the serializer , validat the data , calls .creat, and return the response
    queryset= User.objects.all()
    serializer_class=UserSerializer



User = get_user_model()

def verify_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return JsonResponse({'error': 'Invalid link'}, status=400)

    if default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return JsonResponse({'message': 'Email verified successfully'})
    else:
        return JsonResponse({'error': 'Invalid or expired token'}, status=400)