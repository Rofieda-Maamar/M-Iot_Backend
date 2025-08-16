from django.shortcuts import render
from rest_framework import generics , status
from .serializers import MachineAddSerializer
from rest_framework.response import Response
import csv
import io
from tenants.models import Client
from rest_framework.exceptions import NotFound
from django_tenants.utils import schema_context
# Create your views here.



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
