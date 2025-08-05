from django.shortcuts import render
from .Serializers import AdminDeactivateSerializer, AdminDetailSerializer, AdminListSerializer, AdminUpdateSerializer, UserSerializer , ChangePasswordSerializer , AdminSerializer
from rest_framework import generics ,filters
from .models import User , Admin
from django.utils.http import urlsafe_base64_decode
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from rest_framework.permissions import IsAuthenticated
from users.permissions import IsAdminUser ,  IsAjoutdescomptes

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend

class AddUserView(generics.CreateAPIView) :  # creatApiView hendle : post , call the serializer , validat the data , calls .creat, and return the response
    queryset= User.objects.all()
    serializer_class=UserSerializer
    permission_classes = [IsAuthenticated, IsAjoutdescomptes]

class AddAdminView(generics.CreateAPIView):
    queryset = Admin.objects.all()
    serializer_class = AdminSerializer
    permission_classes = [IsAuthenticated, IsAjoutdescomptes]

class AdminListView(generics.ListAPIView):
    queryset = Admin.objects.select_related('user').all()
    serializer_class = AdminListSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

class AdminDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Admin.objects.select_related('user').all()
    serializer_class = AdminDetailSerializer
    lookup_field = 'id'


class AdminUpdateAPIView(generics.UpdateAPIView):
    queryset = Admin.objects.select_related('user')
    serializer_class = AdminUpdateSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    

class AdminDeactivateAPIView(generics.UpdateAPIView):
    queryset = Admin.objects.all()
    serializer_class = AdminDeactivateSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

   
class AdminSearchAPIView(generics.ListAPIView):
    queryset = Admin.objects.select_related('user').all()
    serializer_class = AdminListSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    filter_backends = [filters.SearchFilter, DjangoFilterBackend]

    # Full-text search
    search_fields = ['nom', 'prenom', 'user__email', 'user__telephone', 'status', 'role']

    # Exact match filters (optional if you want ?status=active for example)
    filterset_fields = ['status', 'role']
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
    
