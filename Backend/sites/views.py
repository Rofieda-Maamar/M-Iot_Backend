from django.shortcuts import render
from rest_framework import generics
from .models import Site
from tenants.models import Client
from .serializers import SiteSerializer , SiteDisplaySerializer , SiteUpdateSerializer
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError, NotFound

from rest_framework.response import Response


class CreatSiteView (generics.CreateAPIView) : 
    serializer_class = SiteSerializer

    #giving the schema_name in the context for the serializer 
    def get_serializer_context(self):
        context = super().get_serializer_context()
        #  getting schema_name from query  URL
        client_id = self.request.query_params.get("client_id")
        if not client_id:
            raise ValidationError("client_id is required to list sites for a tenant.")

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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        client_id = self.request.query_params.get("client_id")
        if not client_id:
            raise ValidationError("client_id is required to list sites for a tenant.")

        try : 
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist: 
            raise NotFound("Client with this id was not found")
        
        # Add schema name to context
        context['schema_name'] = client.schema_name
        return context

    def list(self, request, *args, **kwargs):
        schema_name = self.get_serializer_context().get('schema_name')
        site_id = request.query_params.get("site_id")
        with schema_context(schema_name):
            queryset = Site.objects.filter(id=site_id)
            if site_id : 
                queryset = queryset.filter(id=site_id)
            serializer = self.get_serializer(queryset , many = True)
            return Response(serializer.data)
        

class UpdateSiteDetail(generics.UpdateAPIView) :
    serializer_class = SiteUpdateSerializer
    queryset = Site.objects.all() 

    def get_serializer_context(self):
        context = super().get_serializer_context()
        client_id = self.request.query_params.get("client_id")
        if not client_id:
            raise ValidationError("client_id is required to update the site")

        try : 
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist: 
            raise NotFound("Client with this id was not found")
        
        # Add schema name to context
        context['schema_name'] = client.schema_name
        return context
    
    def get_object(self):
        schema_name = self.get_serializer_context().get('schema_name')
        site_id = self.request.query_params.get("site_id") or self.kwargs.get("pk")

        if not site_id:
            raise ValidationError("site_id or pk is required to update a site")

        with schema_context(schema_name):
            try:
                return Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                raise NotFound("Site with this id was not found in tenant schema")
            
    def update(self, request, *args, **kwargs):
        schema_name = self.get_serializer_context().get('schema_name')
        with schema_context(schema_name):
            return super().update(request, *args, **kwargs)