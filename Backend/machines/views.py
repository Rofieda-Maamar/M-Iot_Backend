from django.shortcuts import render
from rest_framework import generics , status
from .serializers import MachineAddSerializer , DisplayMachinesSerializer ,CaptureMachineSerializer
from rest_framework.response import Response
import csv
import io
from tenants.models import Client
from rest_framework.exceptions import ValidationError
from .models import Machine
from rest_framework.exceptions import NotFound
from django_tenants.utils import schema_context
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
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



class CreatMachineView(generics.CreateAPIView) : 
    serializer_class = MachineAddSerializer

    #giving the schema_name in the context for the serializer 
    def get_serializer_context(self):
        context = super().get_serializer_context()
        #  getting client id from query  URL
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

    
class MachineListUploadView(generics.GenericAPIView):
    serializer_class = MachineAddSerializer

    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No CSV file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            decoded_file = file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(decoded_file))
        except Exception as e:
            return Response({"error": f"Invalid File Format: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        
        results = []
        errors = []

        for idx, row in enumerate(csv_reader, start=1):
            machine_data = {
                "site": row["site_id"],
                "identificateur": row["identificateur"],
                "status": row["status"],
                "date_installation": row.get("date_installation"),
                "date_dernier_serv": row.get("date_dernier_serv"),
                "captures": [
                    {
                        "num_serie": row["capture1_num_serie"],
                        "date_install": row["capture1_date_install"],
                        "parametres": [
                            {"nom": row["param1_nom"], "unite": row["param1_unite"], "valeur_max": row["param1_valeur_max"]},
                            {"nom": row["param2_nom"], "unite": row["param2_unite"], "valeur_max": row["param2_valeur_max"]},
                        ]
                    },
                    {
                        "num_serie": row["capture2_num_serie"],
                        "date_install": row["capture2_date_install"],
                        "parametres": [
                            {"nom": row["param3_nom"], "unite": row["param3_unite"], "valeur_max": row["param3_valeur_max"]},
                        ]
                    }
                ]
            }

            serializer = self.get_serializer(data=machine_data)
            if serializer.is_valid():
                serializer.save()
                results.append(serializer.data)
            else:
                errors.append({"row": idx, "errors": serializer.errors})

        return Response({"created": results, "errors": errors}, status=status.HTTP_201_CREATED)


class DisplayMachineView(generics.ListAPIView) : 
    queryset = Machine.objects.all()
    serializer_class = DisplayMachinesSerializer

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
        machine_id = request.query_params.get("machine_id")

        with schema_context(schema_name):
            queryset = Machine.objects.filter(id=machine_id)
            if machine_id : 
                queryset = queryset.filter(id=machine_id)
            serializer = self.get_serializer(queryset , many = True)
            return Response(serializer.data)
