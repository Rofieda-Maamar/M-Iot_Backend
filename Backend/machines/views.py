from django.shortcuts import render

# Create your views here.
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from .Serializers  import CaptureMachineSerializer
from tenants.models import Client  # ton modèle tenant
from django_tenants.utils import schema_context
from machines.models import CaptureMachine
from rest_framework import status

class AllCaptureMachinesView(APIView):
    def get(self, request):
        all_captures = []

        # Parcours de tous les tenants
        for client in Client.objects.all():
            with schema_context(client.schema_name):  # Active le schéma du client
                captures = CaptureMachine.objects.all()
                serializer = CaptureMachineSerializer(captures, many=True)
                # On ajoute une info pour savoir de quel client ça vient
                for item in serializer.data:
                     item['client'] = client.nom_entreprise # ou client.name selon ton modèle
                all_captures.extend(serializer.data)

        return Response(all_captures)



class CaptureMachineSearchView(APIView):
    def get(self, request):
        num_serie = request.query_params.get('num_serie')
        if not num_serie:
            return Response({"detail": "Paramètre 'num_serie' requis."}, status=status.HTTP_400_BAD_REQUEST)

        found_capture = None
        found_client_name = None

        # Parcours de tous les tenants pour chercher le capteur par num_serie
        for client in Client.objects.all():
            with schema_context(client.schema_name):
                try:
                    capture = CaptureMachine.objects.get(num_serie=num_serie)
                    serializer = CaptureMachineSerializer(capture)
                    found_capture = serializer.data
                    found_client_name = client.nom_entreprise
                    break  # On sort dès qu'on trouve le capteur
                except CaptureMachine.DoesNotExist:
                    continue

        if found_capture:
            found_capture['client'] = found_client_name
            return Response(found_capture, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Capteur non trouvé."}, status=status.HTTP_404_NOT_FOUND)
