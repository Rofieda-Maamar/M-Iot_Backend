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
from django.db.models import OuterRef, Subquery
from django.http import StreamingHttpResponse
import time
import json
from django.utils.timezone import now

from django.db.models import Avg
from django.db.models.functions import ExtractMonth
from django.utils import timezone

from django.http import StreamingHttpResponse, HttpResponseBadRequest, HttpResponseNotFound




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

class AllMachinesClientView(APIView):
     

    def get(self, request):
        """Récupérer toutes les machines du client actuel basé sur le schéma tenant"""
        
        try:
            # Utiliser le schéma actuel (depuis le sous-domaine)
            current_schema = connection.schema_name
            print(f"DEBUG MACHINES: Current schema: {current_schema}")
            
            # Récupérer toutes les machines dans le schéma actuel
            machines = Machine.objects.all().order_by('identificateur')
            
            # Obtenir le nom de l'entreprise actuelle
            from tenants.models import Client
            client_actuel = Client.objects.filter(schema_name=current_schema).first()
            
            machines_data = []
            for machine in machines:
                machine_info = {
                    'identificateur': machine.identificateur
                }
                machines_data.append(machine_info)
            
            return Response({
                'count': len(machines_data),
                'entreprise': client_actuel.nom_entreprise if client_actuel else "Entreprise inconnue",
                'machines': machines_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"DEBUG MACHINES: Erreur lors de la récupération: {e}")
            return Response({
                "detail": f"Erreur lors de la récupération des machines: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        



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



class DisplayMachineDetailView(generics.ListAPIView) : 
    queryset = Machine.objects.all()
    serializer_class = DisplayMachinesDetailSerializer

    def get_queryset(self):
        site_id = self.request.query_params.get("site_id")
        if not site_id : 
            raise ValidationError("site_id required")
        try : 
            Site.objects.get(id=site_id)
        except Site.DoesNotExist : 
            raise ValidationError("site with this id doesn't exist")
        
        queryset = Machine.objects.filter(site= site_id)
        return queryset




class MachineUploadView(APIView):
    """
    Upload CSV/Excel to create Machines with captures/parameters.
    Expected columns:
      identificateur, status, machine_date,
      capt_num_serie, capt_date_install,
      param_nom, param_unite, param_valeur_max
    """

    REQUIRED_COLS = [
        'identificateur', 'status', 'machine_date_install',
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
                        serializer = MachineAddSerializer(data=payload, context={"schema_name": client.schema_name})
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
                "date_installation": self._safe_datetime_iso(r.get("machine_date_install")),
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




#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ dashboard  Machine views ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  


class MachineDashboardView(generics.RetrieveAPIView) :
    queryset = Machine.objects.all()
    serializer_class = MachineDashboardSerializer



def  MachineCapturesLastValuesSSEView(request , machine_id):
   
    PARAM_NAMES = [ # a fixed list of all possible parameters. Used to 
        #ensure every capture has the same fields, even if some parameters dont exist for that capture
        'temperateur', 'luminosite', 'humidite',
        'vibration', 'voltage', 'pression', 'amperage'
    ]

    
        # fetch the machine by its id 
    try:
        machine = Machine.objects.get(id=machine_id)
    except Machine.DoesNotExist:
        return StreamingHttpResponse(
            'data: {"error": "Machine not found"}\n\n',
            content_type='text/event-stream',
            status=404
        )

    def event_stream(): 
        while True: # Infinite loop: keeps the connection open and sends updates repeatedly.
                #a Subquery returns the latest timestamp for the current capture.
            last_time_subq = Subquery( 
                MachineParametre.objects
                    .filter(parametre__captureMachine=OuterRef('pk')) # all MachineParametre objects whose parametre belongs to this capture
                    .order_by('-date_heure') # Orders the records from newest to oldest.
                    .values('date_heure')[:1] # Only pick the latest timestamp (date_heure)
            )
            captures_qs = CaptureMachine.objects.filter(machine=machine).annotate(
                last_read_time=last_time_subq # After this annotation, each CaptureMachine object now has a .last_read_time property, which is the most recent measurement time among all its parameters.
            )
                # Subquery to fetch latest value for each Parametre.
            latest_val_subq = Subquery(
                MachineParametre.objects
                    .filter(parametre=OuterRef('pk'))
                    .order_by('-date_heure')
                    .values('valeur')[:1]
            )

                # build the result for each capture 
            results = []
            for capture in captures_qs:
                params_qs = Parametre.objects.filter(captureMachine=capture).annotate(latest_val=latest_val_subq)
                param_values = {name: "-" for name in PARAM_NAMES} #Initialize all parameters to "-" first.
                for p in params_qs:
                    param_values[p.nom] = p.latest_val if p.latest_val is not None else "-"

                        #temps is the last recorded time for the capture.
                temps = capture.last_read_time.isoformat() if capture.last_read_time else None
                    #out combines the capture info + latest values for all parameters.
                out = {"num_serie": capture.num_serie, "temps": temps}
                out.update(param_values)
                results.append(out) # Append to results list.

                # Send result to client via sse 
            yield f"data: {json.dumps(results)}\n\n"

                # Wait before sending next update
            time.sleep(5)  

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    


def machine_params_sse(request, machine_id):
    """
    SSE endpoint that streams last values of parameters for all captures of a given machine.
    """

    def event_stream():
        while True:
            #  Get captures of this machine
            captures = CaptureMachine.objects.filter(machine_id=machine_id)

            # Subquery to get last MachineParametre value for each parametre
            last_value_subquery = MachineParametre.objects.filter(
                parametre=OuterRef("pk")
            ).order_by("-date_heure").values("valeur")[:1]

            #  Build the response
            data = []
            for capture in captures:
                params = Parametre.objects.filter(captureMachine=capture).annotate(
                    last_valeur=Subquery(last_value_subquery)
                )
                for p in params:
                    data.append({
                        "capture_id": capture.id,
                        "parametre_nom": p.nom,
                        "unite": p.unite,
                        "val_max" : p.valeur_max ,
                        "last_valeur": p.last_valeur,
                    })

            # --- Step 4: Send as SSE event
            yield f"data: {json.dumps(data, default=str)}\n\n"

            time.sleep(2)  # stream every 2 seconds

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    return response




def machine_temperature_stats_stream(request):
    """
    SSE endpoint that:
    - expects ?machine_id=<id>
    - checks machine exists and has captures
    - selects captures that have Parametre(s) with nom='temperateur'
    - for each such capture, computes monthly avg for current year and last year
    - streams JSON every 5 seconds
    """
    machine_id = request.GET.get("machine_id")
    if not machine_id:
        return HttpResponseBadRequest(
            json.dumps({"error": "machine_id is required"}),
            content_type="application/json",
        )

    #  Check machine existence
    try:
        machine = Machine.objects.get(pk=machine_id)
    except Machine.DoesNotExist:
        return HttpResponseNotFound(
            json.dumps({"error": "Machine not found"}),
            content_type="application/json",
        )

    #  Check machine has captures
    if not machine.captures.exists():
        return HttpResponseNotFound(
            json.dumps({"error": "This machine has no captures"}),
            content_type="application/json",
        )

    #  Find Parametre objects linked to captures of this machine with nom 'temperateur'
    # -> use case-insensitive comparison to avoid mismatch
    temp_params_qs = Parametre.objects.filter(captureMachine__machine=machine, nom__iexact="temperature")

    if not temp_params_qs.exists():
        return HttpResponseNotFound(
            json.dumps({"error": "No captures with a 'temperateur' parameter for this machine"}),
            content_type="application/json",
        )

    #  Ensure there is at least one MachineParametre measurement for current or last year
    current_year = timezone.now().year
    last_year = current_year - 1

    has_values = MachineParametre.objects.filter(
        parametre__in=temp_params_qs,
        date_heure__year__in=(current_year, last_year)
    ).exists()

    if not has_values:
        return HttpResponseNotFound(
            json.dumps(
                {
                    "error": "No temperature measurements found for this machine "
                             f"for years {last_year} or {current_year}"
                }
            ),
            content_type="application/json",
        )

    def _to_number_or_none(v):
        if v is None:
            return None
        try:
            return float(round(v, 2))
        except Exception:
            return None
        
    # SSE generator
    def event_stream():
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        while True:
            cy = timezone.now().year
            ly = cy - 1

            # Query agrégée pour l'année courante (moyenne par mois)
            this_year_qs = (
                MachineParametre.objects
                .filter(parametre__in=temp_params_qs, date_heure__year=cy)
                .annotate(month=ExtractMonth("date_heure"))
                .values("month")
                .annotate(moy=Avg("valeur"))
                .order_by("month")
            )
            last_year_qs = (
                MachineParametre.objects
                .filter(parametre__in=temp_params_qs, date_heure__year=ly)
                .annotate(month=ExtractMonth("date_heure"))
                .values("month")
                .annotate(moy=Avg("valeur"))
                .order_by("month")
            )

            this_year_dict = {item["month"]: item["moy"] for item in this_year_qs}
            last_year_dict = {item["month"]: item["moy"] for item in last_year_qs}

            # Construire la liste finale  : un objet par mois
            months_payload = []
            for m in range(1, 13):
                months_payload.append({
                    "month": months[m - 1],
                    "this-year": _to_number_or_none(this_year_dict.get(m)),
                    "last-year": _to_number_or_none(last_year_dict.get(m)),
                })

            response_obj = {
                "data": months_payload
            }

            yield f"data: {json.dumps(response_obj, default=str)}\n\n"

            time.sleep(5)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response