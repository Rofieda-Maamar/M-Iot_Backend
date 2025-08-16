from django.shortcuts import render
from rest_framework import generics , status
from .models import ClientUser 
from .serializers import ClientUserSerializer ,displayListUsersClientSerializer
import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError , NotFound
from tenants.models import Client
from django_tenants.utils import schema_context
from sites.models import Site

class AddClientUserView(generics.CreateAPIView):
    serializer_class=ClientUserSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context() 
        client_id = self.request.query_params.get('client_id') #retrive the client id from the urm
        # Pass schema_name to serializer from client_id query param
        if not client_id : 
            raise ValidationError("client_id is required")
        
        try : 
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist : 
            raise NotFound("client with this id not found")
        context['schema_name'] = client.schema_name
        return context
# Create your views here.


class UploadClientUserView(APIView):


    """
    Upload an Excel file with multiple users.
    File should have columns: email, password, telephone, role
    """
    
    def post(self, request, format=None):
        client_id = request.query_params.get("client_id")
        if not client_id : 
            raise ValidationError("client id is required ")

        try : 
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist : 
            raise NotFound("client with this id not found ")
        
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Read Excel into pandas DataFrame
            df = pd.read_excel(file)
            # Convert rows to list of dicts
            users_data = df.to_dict(orient='records')
        except Exception as e:
            return Response({"error": f"Invalid file format: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        created_users = []
        errors = []

        required_columns = ['email', 'password', 'telephone', 'role']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return Response(
                {"error": f"Missing required columns: {', '.join(missing_columns)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with schema_context(client.schema_name):

            for i, user_data in enumerate(users_data):
                serializer = ClientUserSerializer(data=user_data , context = {"schema_name" : client.schema_name})
                if serializer.is_valid():
                    serializer.save()
                    created_users.append(serializer.data)
                else:
                    errors.append({"row": i+1, "errors": serializer.errors})

        if errors:
            return Response({"created": created_users, "errors": errors}, status=status.HTTP_207_MULTI_STATUS)

        return Response({"created": created_users}, status=status.HTTP_201_CREATED)
    

class displayListUsersClientView(APIView) :
    serializer_class = displayListUsersClientSerializer
    def get(self, request, *args, **kwargs):
        client_id = request.query_params.get("client_id")
        site_id = kwargs.get("pk") or request.query_params.get("site_id")
        if not client_id:
            raise ValidationError("client_id is required")

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            raise NotFound("Client with this id was not found")
        

        schema_name = client.schema_name

        # ✅ Ensure query is executed inside schema_context
        with schema_context(schema_name):
            users = ClientUser.objects.filter(site_id=site_id)
            if not users.exists() : 
                raise NotFound("No user found for this Site")

            serializer =  self.serializer_class(users, many=True)
            return Response(serializer.data)
