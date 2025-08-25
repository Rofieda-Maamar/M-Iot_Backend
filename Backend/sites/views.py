from django.shortcuts import render
from rest_framework import generics
from .models import Site
from tenants.models import Client
from .serializers import *
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from captures.models import TypeParametre , TagRfid
from datetime import datetime
from dateutil import parser as date_parser
from collections import defaultdict
import pandas as pd
from rest_framework import status
from django.db import transaction
from django.db.models.functions import ExtractMonth
from captures.models import *
from django.db.models import Avg
from rest_framework.exceptions import ParseError



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
        
class SiteCapturesDisplayView(APIView) : 
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
            try:
                site = Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                raise NotFound("Site not found")

            serializer = SiteCapturesDisplaySerializer(site)
            return Response(serializer.data)


class SitePositionView(generics.RetrieveAPIView) : 
    queryset = Site.objects.all()
    serializer_class = SitePositionSerializer



class SiteUploadView(APIView):
    """
    Excel columns expected (exact names):
      nom, adresse, latitude, longitude, asset_tracking,
      capture_num_serie, capture_date_install,
      param_nom, param_unite, param_valeur_max
    Produces for each site a payload matching SiteSerializer:
    {
      "nom": ...,
      "adresse": ...,
      "latitude": ...,
      "longitude": ...,
      "asset_tracking": ...,
      "captures": [
         {
           "num_serie": ...,
           "date_install": ...,
           "parametres": [ { "nom":..., "unite":..., "valeur_max": ... }, ... ]
         },
         ...
      ]
    }
    """

    REQUIRED_COLS = [
        'nom', 'adresse', 'latitude', 'longitude', 'asset_tracking',
        'capture_num_serie', 'capture_date_install',
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

        file = request.FILES.get('file')
        if not file:
            raise ParseError("No file uploaded in 'file' field")

        try:
            df = pd.read_excel(file)
        except Exception as e:
            return Response({"error": f"Cannot read excel file: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate columns
        missing = [c for c in self.REQUIRED_COLS if c not in df.columns]
        if missing:
            return Response({"error": f"Missing columns: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)

        rows = df.to_dict(orient='records')
        site_payloads = self._group_rows_into_sites(rows)

        created = []
        errors = []

        # All DB writes done inside tenant schema
        with schema_context(client.schema_name):
            for payload in site_payloads:
                try:
                    with transaction.atomic():
                        serializer = SiteSerializer(data=payload, context={'schema_name': client.schema_name})
                        if serializer.is_valid():
                            site_obj = serializer.save()
                            created.append({"site_id": site_obj.id, "nom": getattr(site_obj, 'nom', None)})
                        else:
                            errors.append({"site": payload.get('nom'), "errors": serializer.errors})
                except Exception as e:
                    errors.append({"site": payload.get('nom'), "errors": str(e)})

        resp = {"created_sites": len(created), "failed": len(errors), "sites": created}
        if errors:
            resp['errors'] = errors
            return Response(resp, status=status.HTTP_207_MULTI_STATUS)
        return Response(resp, status=status.HTTP_201_CREATED)


    # -------- helpers --------
    def _group_rows_into_sites(self, rows):
        """
        Convert flat rows into list of site payloads expected by SiteSerializer.
        Uses 'captures' -> each capture contains 'parametres' list.
        """
        sites = {}
        for r in rows:
            site_name = str(r.get('nom', '')).strip()
            if not site_name:
                continue

            # Initialize site if first time
            if site_name not in sites:
                sites[site_name] = {
                    "nom": site_name,
                    "adresse": r.get('adresse', '') or '',
                    "latitude": self._safe_float(r.get('latitude')),
                    "longitude": self._safe_float(r.get('longitude')),
                    "asset_tracking": self._safe_bool(r.get('asset_tracking')),
                    "captures": []
                }

            capture_serial = str(r.get('capture_num_serie', '')).strip()
            if not capture_serial:
                continue

            # find existing capture in this site payload
            captures = sites[site_name]['captures']
            cap = next((c for c in captures if c['num_serie'] == capture_serial), None)
            if cap is None:
                cap = {
                    "num_serie": capture_serial,
                    # date_install as ISO string or datetime; serializers often accept both
                    "date_install": self._safe_date_iso(r.get('capture_date_install')),
                    "parametres": []
                }
                captures.append(cap)

            param_nom = str(r.get('param_nom', '')).strip()
            if param_nom:
                # avoid duplicates
                if not any(p['nom'] == param_nom for p in cap['parametres']):
                    cap['parametres'].append({
                        "nom": param_nom,
                        "unite": r.get('param_unite', '') or '',
                        "valeur_max": self._safe_float(r.get('param_valeur_max'))
                    })

        # return list of payloads
        return list(sites.values())

    def _safe_float(self, v):
        try:
            if v is None:
                return None
            # pandas NA check
            if isinstance(v, float) and pd.isna(v):
                return None
            return float(v)
        except Exception:
            return None

    def _safe_bool(self, v):
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s in ('1', 'true', 'yes', 'y', 'oui')

    def _safe_date_iso(self, v):
        """
        Return an ISO date string acceptable by serializers (YYYY-MM-DD or full ISO).
        If cannot parse, returns None.
        """
        if v is None:
            return None
        # if already datetime
        if isinstance(v, datetime):
            dt = v
        else:
            try:
                # pandas often returns Timestamp; pd.to_datetime handles many formats
                dt = pd.to_datetime(v, errors='coerce')
                if pd.isna(dt):
                    dt = date_parser.parse(str(v))
            except Exception:
                return None

        # ensure aware or naive depending on your serializers; here we return date string (no tz)
        try:
            return dt.date().isoformat()
        except Exception:
            # fallback to string
            return str(v)
        



from django.http import StreamingHttpResponse
import json, time


def Temperature_stats_stream(request):
    
    site_id = request.GET.get("site_id")
    if not site_id:
        return StreamingHttpResponse({"error": "site_id is required"}, status=400)
        # 1. Get the TypeParametre for temperature in this site

    def event_stream() :
        while True : 
            try:
                temp_param = TypeParametre.objects.get(site_id=site_id, nom="temperateur")
            except TypeParametre.DoesNotExist:
                return Response({"error": "Temperature parameter not found for this site"}, status=404)

        # 2. Filter SiteParametre for this TypeParametre
            qs = SiteParametre.objects.filter(typeParametre=temp_param)

        # Current and last year
            current_year = datetime.now().year
            last_year = current_year - 1

        # 3. Aggregate by month for this year
            this_year_data = (
                qs.filter(date_heure__year=current_year)
                .annotate(month=ExtractMonth("date_heure"))
                .values("month")
                .annotate(moy=Avg("valeur"))
            )

        # 4. Aggregate by month for last year
            last_year_data = (
                qs.filter(date_heure__year=last_year)
                .annotate(month=ExtractMonth("date_heure"))
                .values("month")
                .annotate(moy=Avg("valeur"))
            )

        # Convert to dicts for quick lookup
            this_year_dict = {item["month"]: item["moy"] for item in this_year_data}
            last_year_dict = {item["month"]: item["moy"] for item in last_year_data}

                # Month names
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]

        # 5. Build response structure
            results = []
            for i, month_name in enumerate(months, start=1):
                results.append({
                    "month": month_name,
                    "this_year": this_year_dict.get(i, 0),
                    "last_year": last_year_dict.get(i, 0),
                })
            
            # Send as SSE
            yield f"data: {json.dumps(results)}\n\n"
            time.sleep(5)  
    return StreamingHttpResponse(event_stream(), content_type="text/event-stream")
