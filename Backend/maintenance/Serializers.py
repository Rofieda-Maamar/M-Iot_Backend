from django.db import connection
from rest_framework import serializers
from machines.models import CaptureMachine
from .models import FichierMaintenanceClient, MaintenanceAdmin, FichierMaintenanceAdmin, MaintenanceClient
from users.models import Admin
from django_tenants.utils import schema_context
from tenants.models import Client


class FichierMaintenanceAdminSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)  # For file upload
    
    class Meta:
        model = FichierMaintenanceAdmin
        fields = ['file', 'url']
        extra_kwargs = {
            'url': {'read_only': True}  # URL will be generated automatically
        }


class MaintenanceAdminListSerializer(serializers.ModelSerializer):
    num_maintenance = serializers.SerializerMethodField()
    capteur_num_serie = serializers.CharField(source='capture_machine.num_serie', read_only=True)
    machine_identificateur = serializers.CharField(source='capture_machine.machine.identificateur', read_only=True)
    client = serializers.SerializerMethodField()
    detail_link = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceAdmin
        fields = [
            'num_maintenance',
            'capteur_num_serie', 
            'machine_identificateur', 
            'client', 
            'date_intervention', 
            'type',
            'detail_link'
        ]

    def get_num_maintenance(self, obj):
        return f"MNT-{obj.id:04d}-{obj.capture_machine.num_serie}"

    def get_client(self, obj):
        # Get client name from context (will be set in the view)
        return self.context.get('client_name', 'Unknown')

    def get_detail_link(self, obj):
        request = self.context.get('request')
        capteur_num_serie = obj.capture_machine.num_serie
        if request:
            return request.build_absolute_uri(f'/api/maintenance/detail/{capteur_num_serie}/{obj.id}/')
        return f'/api/maintenance/detail/{capteur_num_serie}/{obj.id}/'


class MaintenanceAdminDetailSerializer(serializers.ModelSerializer):
    num_maintenance = serializers.SerializerMethodField()
    capteur_num_serie = serializers.CharField(source='capture_machine.num_serie', read_only=True)
    machine_identificateur = serializers.CharField(source='capture_machine.machine.identificateur', read_only=True)
    client = serializers.SerializerMethodField()
    fichiers = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceAdmin
        fields = [
            'num_maintenance',
            'type',
            'date_intervention',
            'client',
            'machine_identificateur',
            'capteur_num_serie',
            'resume',
            'fichiers'
        ]

    def get_num_maintenance(self, obj):
        return f"MNT-{obj.id:04d}-{obj.capture_machine.num_serie}"

    def get_client(self, obj):
        return self.context.get('client_name', 'Unknown')

    def get_fichiers(self, obj):
        return [fichier.url for fichier in obj.fichiermaintenanceadmin_set.all()]


class MaintenanceAdminCreateSerializer(serializers.ModelSerializer):
    num_serie = serializers.CharField(write_only=True)

    class Meta:
        model = MaintenanceAdmin
        fields = ['num_serie', 'date_intervention', 'type', 'resume']

    def create(self, validated_data):
        capture_machine = self.context.get('capture_machine')
        admin = self.context.get('admin')
        request = self.context.get('request')

        print(f"DEBUG: Request FILES: {request.FILES}")
        print(f"DEBUG: Request DATA: {request.data}")

        maintenance = MaintenanceAdmin.objects.create(
            admin=admin,
            capture_machine=capture_machine,
            date_intervention=validated_data['date_intervention'],
            type=validated_data['type'],
            resume=validated_data['resume'],
        )
        
        print(f"DEBUG: Maintenance created with ID: {maintenance.id}")
        
        # Handle file uploads from request.FILES
        files_uploaded = request.FILES.getlist('files')
        print(f"DEBUG: Files found in request.FILES: {len(files_uploaded)}")
        
        if files_uploaded:
            print(f"DEBUG: Processing {len(files_uploaded)} files")
            for i, uploaded_file in enumerate(files_uploaded):
                print(f"DEBUG: Processing file {i+1}: {uploaded_file.name}")
                try:
                    # Save the file and generate URL
                    import os
                    from django.conf import settings
                    from django.core.files.storage import default_storage
                    
                    # Generate unique filename
                    file_name = f"maintenance/{maintenance.id}/{uploaded_file.name}"
                    print(f"DEBUG: Saving file as: {file_name}")
                    file_path = default_storage.save(file_name, uploaded_file)
                    file_url = default_storage.url(file_path)
                    print(f"DEBUG: File saved at: {file_path}, URL: {file_url}")
                    
                    fichier_obj = FichierMaintenanceAdmin.objects.create(
                        maintenance=maintenance, 
                        url=file_url
                    )
                    print(f"DEBUG: FichierMaintenanceAdmin created with ID: {fichier_obj.id}")
                except Exception as e:
                    print(f"DEBUG: Error saving file {i+1}: {e}")
        else:
            print("DEBUG: No files found in request.FILES")
        
        return maintenance


class SearchResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    filters_applied = serializers.DictField()
    results = MaintenanceAdminListSerializer(many=True)


# Ajouter ces nouveaux serializers à la fin du fichier existant

class FichierMaintenanceClientSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)  # For file upload
    
    class Meta:
        model = FichierMaintenanceClient
        fields = ['file', 'url']
        extra_kwargs = {
            'url': {'read_only': True}  # URL will be generated automatically
        }


class MaintenanceClientListSerializer(serializers.ModelSerializer):
    num_maintenance = serializers.SerializerMethodField()
    machine_identificateur = serializers.CharField(source='machine.identificateur', read_only=True)
    client_nom = serializers.SerializerMethodField()
    detail_link = serializers.SerializerMethodField()
    capteurs_machine = serializers.SerializerMethodField() 

    class Meta:
        model = MaintenanceClient
        fields = [
            'id',  
            'num_maintenance',
            'client_id',  
            'machine_identificateur', 
            'client_nom', 
            'date_intervention', 
            'type',
            'capteurs_machine'
            'detail_link'
        ]

    def get_num_maintenance(self, obj):
        return f"MNT-CLIENT-{obj.id:04d}-{obj.machine.identificateur}"

    def get_client_nom(self, obj):
        client_user = obj.client
        user = client_user.get_user()
        return f"{user.first_name} {user.last_name}" if user else "Client Inconnu"

    def get_detail_link(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/maintenance/detail-client/{obj.machine.identificateur}/{obj.id}/')
        return f'/api/maintenance/detail-client/{obj.machine.identificateur}/{obj.id}/'

    def get_capteurs_machine(self, obj):
        """Obtenir les numéros de série des capteurs associés à cette machine"""
        
        capteurs = CaptureMachine.objects.filter(machine=obj.machine)
        return [capteur.num_serie for capteur in capteurs]
    

class MaintenanceClientListSerializer(serializers.ModelSerializer):
    num_maintenance = serializers.SerializerMethodField()
    machine_identificateur = serializers.CharField(source='machine.identificateur', read_only=True)
    client_nom = serializers.SerializerMethodField()
    detail_link = serializers.SerializerMethodField()

 
    class Meta:
        model = MaintenanceClient
        fields = [
            'id',  
            'num_maintenance',
            'client_id',  
            'machine_identificateur', 
            'client_nom', 
            'date_intervention', 
            'type',
            'detail_link'
           
        ]

    def get_num_maintenance(self, obj):
        return f"MNT-CLIENT-{obj.id:04d}-{obj.machine.identificateur}"

    def get_client_nom(self, obj):
        client_user = obj.client
        user = client_user.get_user()
        return f"{user.first_name} {user.last_name}" if user else "Client Inconnu"

    def get_detail_link(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/maintenance/detail-client/{obj.machine.identificateur}/{obj.id}/')
        return f'/api/maintenance/detail-client/{obj.machine.identificateur}/{obj.id}/'


class MaintenanceClientCreateSerializer(serializers.ModelSerializer):
    machine_identificateur = serializers.CharField(write_only=True)

    class Meta:
        model = MaintenanceClient
        fields = ['machine_identificateur', 'date_intervention', 'type', 'resume']

    def create(self, validated_data):
        machine = self.context.get('machine')
        client_user = self.context.get('client_user')
        request = self.context.get('request')

        print(f"DEBUG CLIENT: Request FILES: {request.FILES}")
        print(f"DEBUG CLIENT: Request DATA: {request.data}")

        maintenance = MaintenanceClient.objects.create(
            client=client_user,
            machine=machine,
            date_intervention=validated_data['date_intervention'],
            type=validated_data['type'],
            resume=validated_data['resume'],
        )
        
        print(f"DEBUG CLIENT: Maintenance created with ID: {maintenance.id}")
        
        # Handle file uploads from request.FILES
        files_uploaded = request.FILES.getlist('files')
        print(f"DEBUG CLIENT: Files found in request.FILES: {len(files_uploaded)}")
        
        if files_uploaded:
            print(f"DEBUG CLIENT: Processing {len(files_uploaded)} files")
            for i, uploaded_file in enumerate(files_uploaded):
                print(f"DEBUG CLIENT: Processing file {i+1}: {uploaded_file.name}")
                try:
                    # Save the file and generate URL
                    import os
                    from django.conf import settings
                    from django.core.files.storage import default_storage
                    
                    # Generate unique filename
                    file_name = f"maintenance_client/{maintenance.id}/{uploaded_file.name}"
                    print(f"DEBUG CLIENT: Saving file as: {file_name}")
                    file_path = default_storage.save(file_name, uploaded_file)
                    file_url = default_storage.url(file_path)
                    print(f"DEBUG CLIENT: File saved at: {file_path}, URL: {file_url}")
                    
                    fichier_obj = FichierMaintenanceClient.objects.create(
                        maintenance=maintenance, 
                        url=file_url
                    )
                    print(f"DEBUG CLIENT: FichierMaintenanceClient created with ID: {fichier_obj.id}")
                except Exception as e:
                    print(f"DEBUG CLIENT: Error saving file {i+1}: {e}")
        else:
            print("DEBUG CLIENT: No files found in request.FILES")
        
        return maintenance