from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from django_tenants.utils import schema_context, get_tenant_model

from machines.models import CaptureMachine
from users.models import Admin , User
from maintenance.models import MaintenanceAdmin, FichierMaintenanceAdmin
from .Serializers import MaintenanceAdminCreateSerializer, FichierMaintenanceAdminSerializer, MaintenanceAdminListSerializer, MaintenanceAdminDetailSerializer, SearchResponseSerializer
from tenants.models import Client  # ton modèle tenant
from django_tenants.utils import schema_context

from users.permissions import IsAdminUser  # ta permission personnalisée


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from tenants.models import Client
from django_tenants.utils import schema_context
from users.permissions import IsAdminUser
from users.models import Admin  # Always import from public schema

class AddMaintenanceAdminView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        print(f"DEBUG VIEW: Request data: {request.data}")
        print(f"DEBUG VIEW: Request files: {request.FILES}")
        
        num_serie = request.data.get('num_serie')
        if not num_serie:
            return Response({"detail": "Le champ 'num_serie' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        found_schema = None
        capture_machine = None
        client_found = None

        # Search for the capteur in all tenant schemas
        for client in Client.objects.all():
            try:
                with schema_context(client.schema_name):
                    from machines.models import CaptureMachine
                    capture_machine = CaptureMachine.objects.filter(num_serie=num_serie).first()
                    if capture_machine:
                        found_schema = client.schema_name
                        client_found = client
                        break
            except Exception:
                continue

        if not capture_machine:
            return Response({"detail": "Aucun capteur trouvé avec ce numéro de série."}, status=status.HTTP_404_NOT_FOUND)

        # Create the maintenance in the correct schema
        with schema_context(found_schema):
            # Query Admin in the SAME tenant schema where the capteur is found
            admin_instance = Admin.objects.filter(user__email=request.user.email).first()
            if not admin_instance:
                return Response({"detail": "Admin non trouvé pour l'utilisateur connecté dans ce tenant."}, status=status.HTTP_404_NOT_FOUND)

            admin_id = admin_instance.id
            from maintenance.Serializers import MaintenanceAdminCreateSerializer
            serializer = MaintenanceAdminCreateSerializer(
                data=request.data,
                context={
                    'request': request,
                    'capture_machine': capture_machine,
                    'admin': admin_instance
                }
            )
            if serializer.is_valid():
                maintenance = serializer.save()
                
                # Get all files associated with this maintenance
                fichiers_urls = []
                for fichier in maintenance.fichiermaintenanceadmin_set.all():
                    fichiers_urls.append(fichier.url)
                
                return Response({
                    "id": maintenance.id,
                    "admin_id": admin_id,
                    "date_intervention": maintenance.date_intervention,
                    "type": maintenance.type,
                    "resume": maintenance.resume,
                    "client": client_found.nom_entreprise,
                    "machine": capture_machine.machine.identificateur,
                    "fichiers": fichiers_urls,
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AllMaintenanceAdminView(APIView):
    #permission_classes = [IsAdminUser]
  
    def get(self, request):
        all_maintenances = []
        
        # Search through all tenant schemas
        for client in Client.objects.all():
            try:
                with schema_context(client.schema_name):
                    from maintenance.models import MaintenanceAdmin
                    maintenances = MaintenanceAdmin.objects.all().order_by('-date_intervention')
                    
                    for maintenance in maintenances:
                        serializer = MaintenanceAdminListSerializer(
                            maintenance, 
                            context={
                                'request': request,
                                'client_name': client.nom_entreprise
                            }
                        )
                        all_maintenances.append(serializer.data)
            except Exception as e:
                print(f"Error accessing schema {client.schema_name}: {e}")
                continue
        
        # Sort all maintenances by date_intervention (most recent first)
        all_maintenances.sort(key=lambda x: x['date_intervention'], reverse=True)
        
        return Response({
            "count": len(all_maintenances),
            "maintenances": all_maintenances
        }, status=status.HTTP_200_OK)


class MaintenanceAdminDetailView(APIView):
    #permission_classes = [IsAdminUser]

    def get(self, request, capteur_num_serie, maintenance_id):
        found_schema = None
        capture_machine = None
        client_found = None

        # Search for the capteur in all tenant schemas (same logic as AddMaintenanceAdminView)
        for client in Client.objects.all():
            try:
                with schema_context(client.schema_name):
                    from machines.models import CaptureMachine
                    capture_machine = CaptureMachine.objects.filter(num_serie=capteur_num_serie).first()
                    if capture_machine:
                        found_schema = client.schema_name
                        client_found = client
                        break
            except Exception:
                continue

        if not capture_machine:
            return Response({"detail": "Aucun capteur trouvé avec ce numéro de série."}, status=status.HTTP_404_NOT_FOUND)

        # Search for the maintenance in the correct schema
        with schema_context(found_schema):
            from maintenance.models import MaintenanceAdmin
            maintenance = MaintenanceAdmin.objects.filter(id=maintenance_id).first()
            
            if not maintenance:
                return Response({"detail": "Maintenance non trouvée dans ce client."}, status=status.HTTP_404_NOT_FOUND)

            # Verify that the maintenance belongs to the same capteur
            if maintenance.capture_machine.num_serie != capteur_num_serie:
                return Response({"detail": "Cette maintenance n'appartient pas à ce capteur."}, status=status.HTTP_400_BAD_REQUEST)

            from maintenance.Serializers import MaintenanceAdminDetailSerializer
            serializer = MaintenanceAdminDetailSerializer(
                maintenance,
                context={
                    'request': request,
                    'client_name': client_found.nom_entreprise
                }
            )
            return Response(serializer.data, status=status.HTTP_200_OK)


class SearchMaintenanceAdminView(APIView):
    #permission_classes = [IsAdminUser]

    def get(self, request):
        # Get search parameters from query params
        capteur_num_serie = request.query_params.get('capteur_num_serie', None)
        machine_identificateur = request.query_params.get('machine_identificateur', None)
        client_name = request.query_params.get('client', None)
        date_intervention = request.query_params.get('date_intervention', None)
        type_maintenance = request.query_params.get('type', None)
        num_maintenance = request.query_params.get('num_maintenance', None)
        
        # Check if at least one search parameter is provided
        search_params = [capteur_num_serie, machine_identificateur, client_name, 
                        date_intervention, type_maintenance, num_maintenance]
        
        if not any(search_params):
            return Response({
                "message": "Veuillez fournir au moins un critère de recherche.",
                "available_filters": [
                    "capteur_num_serie", 
                    "machine_identificateur", 
                    "client", 
                    "date_intervention", 
                    "type", 
                    "num_maintenance"
                ],
                "count": 0,
                "maintenances": []
            }, status=status.HTTP_200_OK)
        
        all_maintenances = []
        
        # Search through all tenant schemas
        for client in Client.objects.all():
            try:
                with schema_context(client.schema_name):
                    from maintenance.models import MaintenanceAdmin
                    
                    # Start with all maintenances in this schema
                    maintenances = MaintenanceAdmin.objects.all()
                    
                    # Apply filters if provided
                    if capteur_num_serie:
                        maintenances = maintenances.filter(capture_machine__num_serie__icontains=capteur_num_serie)
                    
                    if machine_identificateur:
                        maintenances = maintenances.filter(capture_machine__machine__identificateur__icontains=machine_identificateur)
                    
                    if date_intervention:
                        maintenances = maintenances.filter(date_intervention=date_intervention)
                    
                    if type_maintenance:
                        maintenances = maintenances.filter(type__icontains=type_maintenance)
                    
                    # Filter by client name if provided
                    if client_name and client_name.lower() not in client.nom_entreprise.lower():
                        continue
                    
                    for maintenance in maintenances:
                        # Filter by num_maintenance if provided (since it's generated dynamically)
                        if num_maintenance:
                            generated_num = f"MNT-{maintenance.id:04d}-{maintenance.capture_machine.num_serie}"
                            if num_maintenance.lower() not in generated_num.lower():
                                continue
                        
                        serializer = MaintenanceAdminListSerializer(
                            maintenance, 
                            context={
                                'request': request,
                                'client_name': client.nom_entreprise
                            }
                        )
                        all_maintenances.append(serializer.data)
                        
            except Exception as e:
                print(f"Error searching in schema {client.schema_name}: {e}")
                continue
        
        # Sort by date_intervention (most recent first)
        all_maintenances.sort(key=lambda x: x['date_intervention'], reverse=True)
        
        # Return only the maintenance results directly
        return Response(all_maintenances, status=status.HTTP_200_OK)