from django.shortcuts import render
from rest_framework.exceptions import ValidationError , NotFound
from django_tenants.utils import schema_context
from django.shortcuts import render
from rest_framework import generics , status
from sites.models import Site
import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
# Create your views here.
from .serializers import TagRfidSerializer 
from rest_framework import generics
from tenants.models import Client


class CreateTagRfidView (generics.CreateAPIView) : 
    serializer_class = TagRfidSerializer

    def get_schema_name(self):
        client_id = self.request.query_params.get('client_id')
        if not client_id:
            raise ValidationError("client id is required")
        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            raise NotFound("client with this id not found")
        return client.schema_name

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['schema_name'] = self.get_schema_name()
        return context

    def create(self, request, *args, **kwargs):
        schema_name = self.get_schema_name()
        with schema_context(schema_name):
            return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        site = serializer.validated_data['site']
        if not site.asset_tracking:
            site.asset_tracking = True
            site.save()
        serializer.save()
    


class UploadTagRfidUserView(APIView):
    """
    Upload an Excel file with multiple tag rfids.
    File should have columns: num_serie, date_install, type (passif , actif)
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
        site_id = request.data.get('site')
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        if not site_id:
            return Response({"error": "No site ID provided"}, status=status.HTTP_400_BAD_REQUEST)
        try :
            df = pd.read_excel(file)
            # Convert rows to list of dicts
            tags_data = df.to_dict(orient='records')
        except Exception as e:
            return Response({"error": f"Invalid file format: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        created_tags = []
        errors = []
        required_columns = ['date_install', 'type', 'num_serie' ]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return Response(
                {"error": f"Missing required columns: {', '.join(missing_columns)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with schema_context(client.schema_name):
            try:
                site = Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                return Response({"error": "Site not found"}, status=status.HTTP_404_NOT_FOUND)

            for i, tag_data in enumerate(tags_data):
                tag_data['site'] = site.id
                # fix date format if needed
                if isinstance(tag_data.get('date_install'), pd.Timestamp):
                    tag_data['date_install'] = tag_data['date_install'].date()
                for key in ['type', 'num_serie']:
                    if tag_data.get(key):
                        tag_data[key] = str(tag_data[key]).strip()
                        
                serializer = TagRfidSerializer(data=tag_data)
                if serializer.is_valid():
                    serializer.save()
                    created_tags.append(serializer.data)
                else:
                    errors.append({"row": i+1, "errors": serializer.errors})

            if created_tags and not site.asset_tracking:
                site.asset_tracking = True
                site.save()

        if errors:
            return Response({"created": created_tags, "errors": errors}, status=status.HTTP_207_MULTI_STATUS)
        return Response({"created": created_tags}, status=status.HTTP_201_CREATED)