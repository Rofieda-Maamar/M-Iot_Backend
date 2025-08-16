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
from tenants.models import Client
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView


from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend

class AddUserView(generics.CreateAPIView) :  # creatApiView hendle : post , call the serializer , validat the data , calls .creat, and return the response
    queryset= User.objects.all()
    serializer_class=UserSerializer
    #permission_classes = [IsAuthenticated, IsAjoutdescomptes]

'''class AddAdminView(generics.CreateAPIView):
    queryset = Admin.objects.all()
    serializer_class = AdminSerializer
    #permission_classes = [IsAuthenticated, IsAjoutdescomptes]
'''
class AddAdminView(generics.CreateAPIView):
    queryset = Admin.objects.all()
    serializer_class = AdminSerializer
    #permission_classes = [IsAuthenticated, IsAjoutdescomptes]

    def perform_create(self, serializer):
        from django_tenants.utils import schema_context
        from tenants.models import Client
        
        # Create admin in public schema
        admin = serializer.save()
        
        # Get the created user and admin data
        user = admin.user
        
        # Add the admin to all existing tenant schemas
        for client in Client.objects.all():
            try:
                with schema_context(client.schema_name):
                    # Check if user already exists in this tenant
                    existing_user = User.objects.filter(email=user.email).first()
                    if not existing_user:
                        # Create user in tenant schema
                        tenant_user = User.objects.create_user(
                            email=user.email,
                            password=user.password,  # Already hashed
                            telephone=user.telephone,
                            role=user.role,
                            logged_in=user.logged_in,
                            logged_out=user.logged_out
                        )
                    else:
                        tenant_user = existing_user
                    
                    # Check if admin already exists for this user in tenant
                    if not Admin.objects.filter(user=tenant_user).exists():
                        Admin.objects.create(
                            user=tenant_user,
                            nom=admin.nom,
                            prenom=admin.prenom,
                            role=admin.role,
                            status=admin.status
                        )
                        print(f"Created admin {admin.nom} {admin.prenom} in tenant {client.schema_name}")
            except Exception as e:
                print(f"Error creating admin in tenant {client.schema_name}: {str(e)}")
                continue
class AdminListView(generics.ListAPIView):
    queryset = Admin.objects.select_related('user').all()
    serializer_class = AdminListSerializer
   # permission_classes = [IsAuthenticated, IsAdminUser]

class AdminDetailView(generics.RetrieveAPIView):
    #permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Admin.objects.select_related('user').all()
    serializer_class = AdminDetailSerializer
    lookup_field = 'id'


class AdminUpdateAPIView(generics.UpdateAPIView):
    queryset = Admin.objects.select_related('user')
    serializer_class = AdminUpdateSerializer
    lookup_field = 'id'
    #permission_classes = [IsAuthenticated, IsAdminUser]
    

class AdminDeactivateAPIView(generics.UpdateAPIView):
    queryset = Admin.objects.all()
    serializer_class = AdminDeactivateSerializer
    lookup_field = 'id'
    #permission_classes = [IsAuthenticated, IsAdminUser]

   
class AdminSearchAPIView(generics.ListAPIView):
    queryset = Admin.objects.select_related('user').all()
    serializer_class = AdminListSerializer
    #permission_classes = [IsAuthenticated, IsAdminUser]

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
    


class CookieTokenRefreshView(TokenRefreshView):
    
    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        # Get refresh token from cookie
        refresh_token = request.COOKIES.get('refreshToken')

        if not refresh_token :
            return Response({'Erreur Hna ': 'Refresh token not provided'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data={'refresh': refresh_token})
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)