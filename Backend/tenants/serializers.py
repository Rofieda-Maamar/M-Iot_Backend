# tenants/serializers.py

from rest_framework import serializers
from .models import Client, Domain
from django.contrib.auth import get_user_model
import re
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from sites.serializers import SiteNameSerializer
from sites.models import Site
from rest_framework.exceptions import ValidationError
from django_tenants.utils import schema_context
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail

User = get_user_model()

class AddClientWithUserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    telephone = serializers.CharField(write_only=True)

    class Meta:
        model = Client
        fields = [
            'email', 'password',
            'nom_entreprise', 'adresse', 'latitude',
            'longitude', 'industrie', 'nom_resp', 'prenom_resp', 'status', 'telephone'
        ]

    @staticmethod
    def generate_schema_name(nom_entreprise):
        import re
        return re.sub(r'\W+', '', nom_entreprise.lower())

    def create(self, validated_data):
        from django_tenants.utils import schema_context
        from users.models import User, Admin

        email = validated_data.pop('email')
        password = validated_data.pop('password')
        telephone = validated_data.pop('telephone')
        nom_entreprise = validated_data.get('nom_entreprise')

        schema_name = self.generate_schema_name(nom_entreprise)

        # Create user instance in public schema with role 'Client'
        user = User.objects.create_user(email=email, password=password, telephone=telephone, role='Client')

        # Create tenant (client)
        client = Client.objects.create(
            user=user,
            schema_name=schema_name,
            **validated_data
        )

        # Create domain for the tenant (client)
        Domain.objects.create(
            domain=f"{schema_name}.localhost",
            tenant=client,
            is_primary=True
        )

        # Get only admin users and their admin data from public schema
        admin_users = list(User.objects.filter(role='admin'))
        public_admins = []
        
        # Create a list of admin data with user email instead of user object
        for admin in Admin.objects.all():
            public_admins.append({
                'user_email': admin.user.email,
                'nom': admin.nom,
                'prenom': admin.prenom,
                'role': admin.role,
                'status': admin.status
            })

        # Copy all users and admins from public schema to tenant schema
        with schema_context(client.schema_name):
            # Copy only admin users
            for admin_user in admin_users:
                try:
                    # Check if user already exists in tenant schema
                    existing_user = User.objects.filter(email=admin_user.email).first()
                    if not existing_user:
                        tenant_user = User.objects.create_user(
                            email=admin_user.email,
                            password=admin_user.password,  # Note: password is hashed
                            telephone=admin_user.telephone,
                            role=admin_user.role,
                            logged_in=admin_user.logged_in,
                            logged_out=admin_user.logged_out
                        )
                    else:
                        tenant_user = existing_user
                    
                    # Copy admin if exists for this user and doesn't already exist
                    public_admin = next((admin for admin in public_admins if admin['user_email'] == admin_user.email), None)
                    if public_admin and not Admin.objects.filter(user=tenant_user).exists():
                        Admin.objects.create(
                            user=tenant_user,
                            nom=public_admin['nom'],
                            prenom=public_admin['prenom'],
                            role=public_admin['role'],
                            status=public_admin['status']
                        )
                        print(f"Created admin for user: {tenant_user.email}")  # Debug line
                except Exception as e:
                    print(f"Error copying user {admin_user.email}: {str(e)}")  # Debug line
                    continue

        # Send verification email to the client email
        

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verify_url = f"http://127.0.0.1:8000/api/user/verify-email/{uid}/{token}/"

        send_mail(
            subject="Verify your email",
            message=f"Welcome to M-IOT!\nClick the link to verify your account:\n{verify_url}",
            from_email='M-IOT <maamarmira005@gmail.com>',
            recipient_list=[email],
            fail_silently=False,
        )

        return client

class ClientListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source = 'user.email' , read_only = True)
    client = serializers.CharField(source='nom_entreprise')
    class Meta:
        model = Client 
        fields = ['id' ,'client' ,'industrie' , 'adresse' , 'email' ]




class ClientDetailSerializer(serializers.ModelSerializer):
    telephone = serializers.CharField(source = 'user.telephone' , read_only = True) 
    email = serializers.EmailField(source = 'user.email' , read_only = True)
    created_at = serializers.DateTimeField(source = 'user.created_at' , read_only = True , format='%Y-%m-%d')
    sites = serializers.SerializerMethodField()

    class Meta:
        model = Client 
        fields = ['id' ,'industrie' ,'latitude' ,'longitude', 'status' , 'telephone', 'email' ,'created_at' , 'sites' ]

    def get_sites(self , obj):
        schema_name = self.context.get('schema_name')
        if not schema_name : 
            raise ValidationError("schema name is required")
        with schema_context(schema_name): 
            sites = Site.objects.all()
            return SiteNameSerializer(sites , many=True).data
    
    def _get_user(self , obj) : 
        # get user from the tennat schema 
        schema_name = self.context.get('schema_name')
        if not schema_name : 
            raise ValidationError('schema name is required')
        with schema_context(schema_name) :
            user = self.instance.user
            return user
    
    def get_telephone(self , obj) : 
        user = self._get_user()
        return getattr(user , 'telephone' ,None) if user else None
    
    def get_email(self , obj) : 
        user = self._get_user()
        return getattr(user , 'email' , None) if user else None
    
    def get_created_at(self, obj):
        user = self._get_user()
        return  user.created_at.strftime('%Y-%m-%d') if user and user.created_at else None
           
        
        



