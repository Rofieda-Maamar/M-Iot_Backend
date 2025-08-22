from django.shortcuts import render
from rest_framework import generics , status
from .serializers import *
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
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound, ParseError
from django.db import transaction
from django_tenants.utils import schema_context
import pandas as pd
from datetime import datetime
from dateutil import parser as date_parser
from django.shortcuts import get_object_or_404
from sites.models import * 


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
                    item['client'] = client.nom_entreprise 
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
        site_id = request.query_params.get("site_id")

        if not site_id : 
            raise ValidationError({"site_id":"required to list machines of this site"})

        with schema_context(schema_name):
            queryset = Machine.objects.filter(site_id=site_id)
            serializer = self.get_serializer(queryset , many = True)
            return Response(serializer.data)



class DisplayMachineDetailView(generics.RetrieveAPIView) : 
    queryset = Machine.objects.all()
    serializer_class = DisplayMachinesDetailSerializer




class MachineUploadView(APIView):
    """
    Upload CSV/Excel to create Machines with captures/parameters.
    Expected columns:
      identificateur, status, machine_date,
      capt_num_serie, capt_date_install,
      param_nom, param_unite, param_valeur_max
    """

    REQUIRED_COLS = [
        'identificateur', 'status', 'machine_date',
        'capt_num_serie', 'capt_date_install',
        'param_nom', 'param_unite', 'param_valeur_max'
    ]

    def post(self, request, format=None):
        client_id = request.query_params.get("client_id")
        if not client_id:
            raise ValidationError("client_id is required")

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            raise NotFound("client with this id not found")
        
        site_id = request.data.get("site_id")
        if not site_id:
            raise ValidationError("site_id is required")

        file = request.FILES.get('file')
        if not file:
            raise ParseError("No file uploaded in 'file' field")

        try:
            df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
        except Exception as e:
            return Response({"error": f"Cannot read file: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        missing = [c for c in self.REQUIRED_COLS if c not in df.columns]
        if missing:
            return Response({"error": f"Missing columns: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)

        payloads = self._group_rows_into_machines(df.to_dict(orient='records'), site_id)

        created, errors = [], []

        with schema_context(client.schema_name):
            try : 
                site = Site.objects.get(id=site_id)

            except Site.DoesNotExist : 
                raise ValidationError("site with this id does not exist")
            for payload in payloads:
                try:
                    with transaction.atomic():
                        serializer = MachineAddSerializer(data=payload, context={"schema_name": schema_name})
                        if serializer.is_valid():
                            obj = serializer.save()
                            created.append({"machine_id": obj.id, "identificateur": obj.identificateur})
                        else:
                            errors.append({"machine": payload["identificateur"], "errors": serializer.errors})
                except Exception as e:
                    errors.append({"machine": payload["identificateur"], "errors": str(e)})

        resp = {
            "created_machines": len(created),
            "failed": len(errors),
            "machines": created,
        }
        if errors:
            resp["errors"] = errors
            return Response(resp, status=status.HTTP_207_MULTI_STATUS)
        return Response(resp, status=status.HTTP_201_CREATED)

    # -------- helpers --------
    def _group_rows_into_machines(self, rows, site_id):
        machines = {}

        for r in rows:
            machine_id = str(r.get("identificateur", "")).strip()
            if not machine_id:
                continue

            machine = machines.setdefault(machine_id, {
                "site": int(site_id),
                "identificateur": machine_id,
                "status": str(r.get("status", "active")).strip(),
                "date_installation": self._safe_datetime_iso(r.get("machine_date")),
                "captures": []
            })

            serial = str(r.get("capt_num_serie", "")).strip()
            if not serial:
                continue

            capture = next((c for c in machine["captures"] if c["num_serie"] == serial), None)
            if not capture:
                capture = {"num_serie": serial,
                           "date_install": self._safe_date_iso(r.get("capt_date_install")),
                           "parametre": []}
                machine["captures"].append(capture)

            param_nom = str(r.get("param_nom", "")).strip()
            if param_nom and not any(p["nom"] == param_nom for p in capture["parametre"]):
                capture["parametre"].append({
                    "nom": param_nom,
                    "unite": r.get("param_unite", "") or "",
                    "valeur_max": self._safe_float(r.get("param_valeur_max"))
                })

        return list(machines.values())

    # ---- parsing helpers ----
    def _safe_float(self, v):
        try:
            return None if v is None or (isinstance(v, float) and pd.isna(v)) else float(v)
        except Exception:
            return None

    def _safe_date_iso(self, v):
        if not v: return None
        try:
            dt = v if isinstance(v, datetime) else pd.to_datetime(v, errors="coerce")
            return None if pd.isna(dt) else dt.date().isoformat()
        except Exception:
            return None

    def _safe_datetime_iso(self, v):
        if not v: return datetime.now().isoformat()
        try:
            dt = v if isinstance(v, datetime) else pd.to_datetime(v, errors="coerce")
            return datetime.now().isoformat() if pd.isna(dt) else dt.isoformat()
        except Exception:
            return datetime.now().isoformat()
