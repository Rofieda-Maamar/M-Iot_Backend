from django.shortcuts import render
from rest_framework import generics
from .models import Site
from tenants.models import Client
from .serializers import SiteSerializer , SiteDisplaySerializer
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError, NotFound



class CreatSiteView (generics.CreateAPIView) : 
    serializer_class = SiteSerializer

    #giving the schema_name in the context for the serializer 
    def get_serializer_context(self):
        context = super().get_serializer_context()
        #  getting schema_name from query  URL
        client_id = self.request.query_params.get("client_id")
        if not client_id:
            raise ValueError("client_id is required to create a site for a tenant.")

        try : 
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist: 
            raise NotFound("Client with this id was not found")
        
        # Add schema name to context
        context['schema_name'] = client.schema_name
        return context
            
    def create(self, request, *args, **kwargs):
        schema_name = self.get_serializer_context().get('schema_name')
        with schema_context(schema_name):
            return super().create(request, *args, **kwargs)


class SiteListView(generics.ListAPIView) : 
    queryset = Site.objects.all()
    serializer_class = SiteDisplaySerializer