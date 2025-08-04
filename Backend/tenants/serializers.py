# tenants/serializers.py

from rest_framework import serializers
from .models import Client, Domain
from django.contrib.auth import get_user_model
import re

User = get_user_model()

class AddClientWithUserSerializer(serializers.ModelSerializer):
    # email , password  to create the user will be associated with the client
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
  #  username = serializers.CharField()

    class Meta:
        model = Client
        fields = [
            'email', 'password',
            'nom_entreprise', 'adresse', 'latitude',
            'longitude', 'industrie', 'nom_resp', 'prenom_resp', 'status'
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
        #username = validated_data.pop('username')
        nom_entreprise = validated_data.get('nom_entreprise')

        # Generate schema_name from company name
        schema_name = self.generate_schema_name(nom_entreprise)

        # Create user instance
        user = User.objects.create_user(email=email, password=password)

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

        return client
