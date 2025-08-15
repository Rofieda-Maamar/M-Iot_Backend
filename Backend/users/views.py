from django.shortcuts import render
from .Serializers import UserSerializer , ChangePasswordSerializer
from rest_framework import generics
from .models import User
from django.utils.http import urlsafe_base64_decode
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from rest_framework.permissions import IsAuthenticated
from tenants.models import Client
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView



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
    

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    model = User
    permission_classes = [IsAuthenticated]

    def get_object(self, queryset=None):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)

            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()

            response = {
                'status': 'success',
                'code': status.HTTP_200_OK,
                'message': "Password updated successfully",
                'data': []
            }
            return Response(response, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


#loginView

## i should ajust for the admin , and userclient
class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user  # Comes from SimpleJWT's validated data
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # find the related client id 
        client_id = user.client_account.id
        subdomain = user.client_account.schema_name
        # Create response data (no refresh token in JSON)
        response_data = {
            'access': access_token ,
            'client_id': client_id ,
            'subdomain' : subdomain ,
            'role' : user.role
        }
        response = Response(response_data)

        # Set refresh token in HTTP-only cookie
        response.set_cookie(
            key='refreshToken',
            value=refresh_token,
            max_age=int(timedelta(days=7).total_seconds()),  # seconds
            httponly=True,
            secure=False,  # change to True in production with HTTPS
            samesite='Strict',
            
        )

        return response