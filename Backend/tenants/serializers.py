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
User = get_user_model()

class AddClientWithUserSerializer(serializers.ModelSerializer):
    # email , password  to create the user will be associated with the client
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    telephone = serializers.CharField(write_only=True)

  #  username = serializers.CharField()

    class Meta:
        model = Client
        fields = [
            'email', 'password',
            'nom_entreprise', 'adresse', 'latitude',
            'longitude', 'industrie', 'nom_resp', 'prenom_resp', 'status' , 'telephone'
        ]

    @staticmethod # the function don't depend to the class , i can call it everywhere 
    def generate_schema_name(nom_entreprise):
        #Removes non-alphanumeric characters from the nom_entrprise 
        # field so i can use it for the schmea_name (and the domain) for this client (tennant)
        #  that will creat
        return re.sub(r'\W+', '', nom_entreprise.lower()) 

    def create(self, validated_data):
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        telephone = validated_data.pop('telephone')
        #username = validated_data.pop('username')
        nom_entreprise = validated_data.get('nom_entreprise')

        # Generate schema_name from company name
        schema_name = self.generate_schema_name(nom_entreprise)

        # Create user instance
        user = User.objects.create_user(email=email, password=password ,telephone=telephone)

        # Create tenant (client)
        client = Client.objects.create(
            user=user,
            schema_name=schema_name,
            **validated_data
        )

        # Create domain for the tenant (client)
        Domain.objects.create(
            domain=f"{schema_name}.localhost",  # for production (deploy) i think somthings must change here
            tenant=client,
            is_primary=True
        )
        
        # Send verification email to the client email
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verify_url = f"http://127.0.0.1:8000/api/user/verify-email/{uid}/{token}/"

        send_mail(
            subject="Verify your email",
            message=f"Welcome to M-IOT!\nClick the link to verify your account:\n{verify_url}",
            from_email='M-IOT <maamarmira005@gmail.com>' ,
            recipient_list=[email],
            fail_silently=False,
        )

        return client
    

class ClientListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source = 'user.email' , read_only = True)
    class Meta:
        model = Client 
        fields = ['id' ,'industrie' , 'latitude' ,'longitude', 'email' , 'nom_entreprise']


class ClientDetailSerializer(serializers.ModelSerializer):
    telephone = serializers.CharField(source = 'user.telephone' , read_only = True) 
    email = serializers.EmailField(source = 'user.email' , read_only = True)
    created_at = serializers.DateTimeField(source = 'user.created_at' , read_only = True , format='%Y-%m-%d')
    sites = serializers.SerializerMethodField()

    class Meta:
        model = Client 
        fields = ['id' ,'industrie' ,'latitude' ,'longitude', 'status' , 'telephone', 'email' ,'created_at' , 'sites' ]

    def get_sites(self , obj):
        sites = Site.objects.all()
        return SiteNameSerializer(sites , many=True).data

