from django.db import connection
from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from django_tenants.utils import schema_context, get_tenant_model

from machines.models import CaptureMachine
from users.models import Admin , User
from maintenance.models import MaintenanceAdmin, FichierMaintenanceAdmin
from .Serializers import MaintenanceAdminCreateSerializer, FichierMaintenanceAdminSerializer, MaintenanceAdminListSerializer, MaintenanceAdminDetailSerializer, MaintenanceClientListSerializer, SearchResponseSerializer
from tenants.models import Client  # ton modèle tenant
from django_tenants.utils import schema_context

from users.permissions import IsAdminUser  # ta permission personnalisée
from machines.models import Machine
from ClientUsers.models import ClientUser
from maintenance.Serializers import MaintenanceClientCreateSerializer
from tenants.models import Client
from maintenance.models import MaintenanceClient

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
    



class AddMaintenanceClientView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        print(f"DEBUG CLIENT VIEW: Request data: {request.data}")
        print(f"DEBUG CLIENT VIEW: Request files: {request.FILES}")
        print(f"DEBUG CLIENT VIEW: User: {request.user}")
        print(f"DEBUG CLIENT VIEW: Current schema: {connection.schema_name}")
        
        machine_identificateur = request.data.get('machine_identificateur')
        if not machine_identificateur:
            return Response({"detail": "Le champ 'machine_identificateur' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        # UTILISER LE SCHÉMA ACTUEL (depuis le sous-domaine)
        current_schema = connection.schema_name
        print(f"DEBUG CLIENT: Using current schema: {current_schema}")
        
        # Chercher la machine dans le schéma actuel seulement
        try:
            machine = Machine.objects.filter(identificateur=machine_identificateur).first()
            
            if not machine:
                return Response({
                    "detail": f"Aucune machine trouvée avec l'identificateur '{machine_identificateur}' dans votre entreprise."
                }, status=status.HTTP_404_NOT_FOUND)
            
            print(f"DEBUG CLIENT: Machine trouvée: {machine.identificateur}")
            
            # Chercher le ClientUser dans le schéma actuel
            client_user = ClientUser.objects.filter(user_id=request.user.id).first()
            
            if not client_user:
                return Response({
                    "detail": "Utilisateur client non trouvé. Vous devez être connecté en tant que client."
                }, status=status.HTTP_404_NOT_FOUND)
            
            print(f"DEBUG CLIENT: ClientUser trouvé: {client_user.id}")
            
            # Créer la maintenance dans le schéma actuel
            serializer = MaintenanceClientCreateSerializer(
                data=request.data,
                context={
                    'request': request,
                    'machine': machine,
                    'client_user': client_user
                }
            )
            
            if serializer.is_valid():
                maintenance = serializer.save()
                
                #  OBTENIR LES CAPTEURS ASSOCIÉS À CETTE MACHINE
                capteurs = CaptureMachine.objects.filter(machine=machine)
                capteurs_num_serie = [capteur.num_serie for capteur in capteurs]
                
                # Obtenir les infos du client actuel
                client_actuel = Client.objects.filter(schema_name=current_schema).first()
                
                # Obtenir les informations utilisateur
                user = client_user.get_user()
                client_nom = f"{user.first_name} {user.last_name}" if user else "Client Inconnu"
                
                # Obtenir tous les fichiers associés à cette maintenance
                fichiers_urls = []
                for fichier in maintenance.fichiermaintenanceclient_set.all():
                    fichiers_urls.append(fichier.url)
                
                return Response({
                    "id": maintenance.id,
                    "num_maintenance": f"MNT-CLIENT-{maintenance.id:04d}-{machine.identificateur}",
                    "client_id": client_user.id,
                    "date_intervention": maintenance.date_intervention,
                    "type": maintenance.type,
                    "resume": maintenance.resume,
                    "client": client_actuel.nom_entreprise if client_actuel else "Entreprise inconnue",
                    "machine": machine.identificateur,
                    "capteurs_machine": capteurs_num_serie,  
                    "fichiers": fichiers_urls,
                    "message": "Maintenance créée avec succès"
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            print(f"DEBUG CLIENT: Erreur lors de la création: {e}")
            return Response({
                "detail": f"Erreur lors de la création de la maintenance: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AllMaintenanceClientView(APIView):
    
  
    def get(self, request):
        # UTILISER SEULEMENT LE SCHÉMA ACTUEL
        current_schema = connection.schema_name
        print(f"DEBUG CLIENT: Listing maintenances for schema: {current_schema}")
        
        try:
            maintenances = MaintenanceClient.objects.all().order_by('-date_intervention')
            
            # Obtenir le nom de l'entreprise actuelle
            client_actuel = Client.objects.filter(schema_name=current_schema).first()
            
            serialized_maintenances = []
            for maintenance in maintenances:
                #  OBTENIR LES CAPTEURS POUR CHAQUE MAINTENANCE
                capteurs = CaptureMachine.objects.filter(machine=maintenance.machine)
                capteurs_num_serie = [capteur.num_serie for capteur in capteurs]
                
                serializer = MaintenanceClientListSerializer(
                    maintenance, 
                    context={
                        'request': request,
                        'client_name': client_actuel.nom_entreprise if client_actuel else "Entreprise inconnue"
                    }
                )
                maintenance_data = serializer.data
                maintenance_data['capteurs_machine'] = capteurs_num_serie 
                serialized_maintenances.append(maintenance_data)
            
            return Response({
                "count": len(serialized_maintenances),
                "entreprise": client_actuel.nom_entreprise if client_actuel else "Entreprise inconnue",
                "maintenances": serialized_maintenances
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"DEBUG CLIENT: Erreur lors de la récupération: {e}")
            return Response({
                "detail": f"Erreur lors de la récupération des maintenances: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MaintenanceClientDetailView(APIView):
   

    def get(self, request, machine_identificateur, maintenance_id):
        # UTILISER SEULEMENT LE SCHÉMA ACTUEL
        current_schema = connection.schema_name
        print(f"DEBUG CLIENT: Getting maintenance detail for schema: {current_schema}")
        
        try:
            # Vérifier que la machine existe dans le schéma actuel
            machine = Machine.objects.filter(identificateur=machine_identificateur).first()
            
            if not machine:
                return Response({
                    "detail": f"Aucune machine trouvée avec l'identificateur '{machine_identificateur}' dans votre entreprise."
                }, status=status.HTTP_404_NOT_FOUND)

            # Chercher la maintenance dans le schéma actuel
            maintenance = MaintenanceClient.objects.filter(id=maintenance_id).first()
            
            if not maintenance:
                return Response({
                    "detail": "Maintenance non trouvée dans votre entreprise."
                }, status=status.HTTP_404_NOT_FOUND)

            # Vérifier que la maintenance appartient à la bonne machine
            if maintenance.machine.identificateur != machine_identificateur:
                return Response({
                    "detail": "Cette maintenance n'appartient pas à cette machine."
                }, status=status.HTTP_400_BAD_REQUEST)

            #  OBTENIR LES CAPTEURS ASSOCIÉS À CETTE MACHINE
            capteurs = CaptureMachine.objects.filter(machine=maintenance.machine)
            capteurs_num_serie = [capteur.num_serie for capteur in capteurs]

            # Obtenir le nom de l'entreprise actuelle
            client_actuel = Client.objects.filter(schema_name=current_schema).first()
            
            # Obtenir les informations du client
            client_user = maintenance.client
            
            # Obtenir tous les fichiers associés à cette maintenance
            fichiers_urls = [fichier.url for fichier in maintenance.fichiermaintenanceclient_set.all()]

            return Response({
                'id': maintenance.id,
                'num_maintenance': f"MNT-CLIENT-{maintenance.id:04d}-{maintenance.machine.identificateur}",
                'client_id': client_user.id,
                'date_intervention': maintenance.date_intervention,
                'type': maintenance.type,
                'resume': maintenance.resume,
                'client': client_actuel.nom_entreprise if client_actuel else "Entreprise inconnue",
                'machine': maintenance.machine.identificateur,
                'capteurs_machine': capteurs_num_serie,  
                'fichiers': fichiers_urls,
                'message': 'Détails de la maintenance récupérés avec succès'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"DEBUG CLIENT: Erreur lors de la récupération du détail: {e}")
            return Response({
                "detail": f"Erreur lors de la récupération du détail: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



