from rest_framework import serializers 
from .models import TypeParametre , CaptureSite , TypeParametre , TagRfid, ObjectTracking, TrackingPoint, PathTemplate, PathTemplatePoint, MesseurTracking , PositionHistorique
from .models import *
from rest_framework.exceptions import ValidationError
from django_tenants.utils import schema_context
from .services import GeolocationService

class TypeParametreSerializer (serializers.ModelSerializer) :
    class Meta : 
        model = TypeParametre 
        fields = [ 'nom' , 'unite' , 'valeur_max']





class CaptureSiteSerializer(serializers.ModelSerializer) : 
    # parametres inside capture bcs multiple parametres can be measured by the same capture 
    parametres = TypeParametreSerializer(many = True)
    status = serializers.ReadOnlyField()
    class Meta : 
        model = CaptureSite
        fields = ['num_serie' , 'date_install' ,  "parametres" , 'status'] 

    def create(self, validated_data):
        parametre_data = validated_data.pop('parametres' , [])
        site = self.context.get('site')
        if site is None:
            raise serializers.ValidationError("site is required in context to create a capture")

        capture = CaptureSite.objects.create(site=site ,**validated_data)
        # creat paramtres related to the site and capture 
        for param in parametre_data : 
            TypeParametre.objects.create(capture=capture , site = site , **param)

        return capture



class ObjectTrackingSerializer(serializers.ModelSerializer):
    class Meta : 
        model=ObjectTracking 
        fields = '__all__'



class TagRfidSerializer(serializers.ModelSerializer) :
    ObjectTracking = ObjectTrackingSerializer(read_only=True)
    categorie = serializers.CharField(write_only=True)

    class Meta : 
        model = TagRfid
        fields = ['site' ,'num_serie' , 'type' ,'date_install']


class TrackingPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingPoint
        fields = ['id', 'nom_lieu', 'latitude', 'longitude']


class ObjectTrackingSerializer(serializers.ModelSerializer):
    nom_objet = serializers.SerializerMethodField()
    
    class Meta:
        model = ObjectTracking
        fields = ['id', 'site', 'capture_RFID', 'categorie', 'etat', 'nom_objet']
    
    def get_nom_objet(self, obj):
        return f"{obj.categorie}_{obj.capture_RFID.num_serie}"


class PathTemplatePointCreateSerializer(serializers.Serializer):
    nom_lieu = serializers.CharField(max_length=200, help_text="Nom du lieu ou adresse")
    latitude = serializers.FloatField(required=False, help_text="Latitude (optionnelle)")
    longitude = serializers.FloatField(required=False, help_text="Longitude (optionnelle)")
    ordre = serializers.IntegerField()
    date_prevu = serializers.DateField()
    
    def validate(self, data):
        geolocation_service = GeolocationService()
        
        try:
            # Traiter la localisation avec le service
            processed_location = geolocation_service.process_location(
                data['nom_lieu'],
                data.get('latitude'),
                data.get('longitude')
            )
            
            # Mettre à jour les données avec les informations traitées
            data['nom_lieu'] = processed_location['nom_lieu']
            data['latitude'] = processed_location['latitude']
            data['longitude'] = processed_location['longitude']
            data['formatted_address'] = processed_location['formatted_address']
            data['verified'] = processed_location['verified']
            
            return data
            
        except ValidationError as e:
            raise serializers.ValidationError(f"Erreur de géolocalisation pour '{data['nom_lieu']}': {str(e)}")


class PlanifierTrajetSerializer(serializers.Serializer):
    nom_trajet = serializers.CharField(max_length=100)
    objet_tracking_nom = serializers.CharField(max_length=100, help_text="Nom de l'objet à tracker (ex: 'Camion_RF001')")
    
    # Source
    source_nom = serializers.CharField(max_length=200, help_text="Nom du lieu ou adresse de départ")
    source_latitude = serializers.FloatField(required=False, help_text="Latitude (optionnelle)")
    source_longitude = serializers.FloatField(required=False, help_text="Longitude (optionnelle)")
    date_prevu_source = serializers.DateField()
    
    # Destination
    destination_nom = serializers.CharField(max_length=200, help_text="Nom du lieu ou adresse de destination")
    destination_latitude = serializers.FloatField(required=False, help_text="Latitude (optionnelle)")
    destination_longitude = serializers.FloatField(required=False, help_text="Longitude (optionnelle)")
    date_prevu_destination = serializers.DateField()
    
    # Points de passage
    points = PathTemplatePointCreateSerializer(many=True)
    
    def validate_objet_tracking_nom(self, value):
        """
        Valide que l'objet existe en cherchant par nom
        """
        if '_' in value:
            categorie, num_serie = value.rsplit('_', 1)
            obj = ObjectTracking.objects.select_related('capture_RFID').filter(
                categorie=categorie,
                capture_RFID__num_serie=num_serie
            ).first()
            
            if not obj:
                raise serializers.ValidationError(f"Aucun objet trouvé avec le nom '{value}'")
        else:
            obj = ObjectTracking.objects.filter(categorie=value).first()
            if not obj:
                raise serializers.ValidationError(f"Aucun objet trouvé avec le nom '{value}'")
        
        return value
    
    def validate(self, data):
        geolocation_service = GeolocationService()
        
        try:
            # Traiter la source
            source_processed = geolocation_service.process_location(
                data['source_nom'],
                data.get('source_latitude'),
                data.get('source_longitude')
            )
            data['source_nom'] = source_processed['nom_lieu']
            data['source_latitude'] = source_processed['latitude']
            data['source_longitude'] = source_processed['longitude']
            data['source_formatted_address'] = source_processed['formatted_address']
            
            # Traiter la destination
            dest_processed = geolocation_service.process_location(
                data['destination_nom'],
                data.get('destination_latitude'),
                data.get('destination_longitude')
            )
            data['destination_nom'] = dest_processed['nom_lieu']
            data['destination_latitude'] = dest_processed['latitude']
            data['destination_longitude'] = dest_processed['longitude']
            data['destination_formatted_address'] = dest_processed['formatted_address']
            
            return data
            
        except ValidationError as e:
            raise serializers.ValidationError(f"Erreur de géolocalisation: {str(e)}")
    
    def create(self, validated_data):
        points_data = validated_data.pop('points')
        objet_tracking_nom = validated_data.pop('objet_tracking_nom')
        
        # Trouver l'objet tracking par son nom
        if '_' in objet_tracking_nom:
            categorie, num_serie = objet_tracking_nom.rsplit('_', 1)
            objet_tracking = ObjectTracking.objects.select_related('capture_RFID').filter(
                categorie=categorie,
                capture_RFID__num_serie=num_serie
            ).first()
        else:
            objet_tracking = ObjectTracking.objects.filter(categorie=objet_tracking_nom).first()
        
        if not objet_tracking:
            raise serializers.ValidationError(f"Objet tracking '{objet_tracking_nom}' non trouvé")
        
        # Créer le PathTemplate avec les coordonnées validées
        path_template = PathTemplate.objects.create(
            nom=validated_data['nom_trajet'],
            source=validated_data['source_nom'],
            destination=validated_data['destination_nom'],
            latitude_src=validated_data['source_latitude'],
            longitude_src=validated_data['source_longitude'],
            latitude_dest=validated_data['destination_latitude'],
            longitude_dest=validated_data['destination_longitude']
        )
        
        # Créer les TrackingPoints avec coordonnées validées
        for point_data in points_data:
            tracking_point, created = TrackingPoint.objects.get_or_create(
                nom_lieu=point_data['nom_lieu'],
                latitude=point_data['latitude'],
                longitude=point_data['longitude']
            )
            
            # Créer le PathTemplatePoint avec la date prévue
            PathTemplatePoint.objects.create(
                template=path_template,
                point=tracking_point,
                ordre=point_data['ordre'],
                date_prevu=point_data['date_prevu']
            )
        
        # Créer le MesseurTracking
        messeur_tracking = MesseurTracking.objects.create(
            capture_rfid=objet_tracking.capture_RFID,
            path=path_template,
            object_tracking=objet_tracking,
            date_debut=validated_data['date_prevu_source'],
            date_fin=validated_data['date_prevu_destination'],
            date_prevu=validated_data['date_prevu_source'],
            lieu=validated_data['source_nom'],
            heure='00:00:00',
            duree_passage='00:00:00'
        )
        
        return {
            'path_template': path_template,
            'messeur_tracking': messeur_tracking,
            'points': PathTemplatePoint.objects.filter(template=path_template),
            'objet_tracking': objet_tracking
        }


class PathTemplateSerializer(serializers.ModelSerializer):
    points = serializers.SerializerMethodField()
    objet_tracking_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = PathTemplate
        fields = ['id', 'nom', 'source', 'destination', 'latitude_src', 
                 'longitude_src', 'latitude_dest', 'longitude_dest', 'points', 'objet_tracking_nom']
    
    def get_points(self, obj):
        path_points = PathTemplatePoint.objects.filter(template=obj).order_by('ordre')
        return [{
            'ordre': pp.ordre,
            'date_prevu': pp.date_prevu,
            'point': TrackingPointSerializer(pp.point).data
        } for pp in path_points]
    
    def get_objet_tracking_nom(self, obj):
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.object_tracking:
            return f"{messeur.object_tracking.categorie}_{messeur.object_tracking.capture_RFID.num_serie}"
        return None

'''
class TrajetListSerializer(serializers.ModelSerializer):
    """
    Serializer pour lister tous les trajets avec informations temps réel
    """
    nom_trajet = serializers.CharField(source='nom')
    objet_nom = serializers.SerializerMethodField()
    capteur_num_serie = serializers.SerializerMethodField()
    etat_objet = serializers.SerializerMethodField()
    localisation_actuelle = serializers.SerializerMethodField()
    latitude_actuelle = serializers.SerializerMethodField()
    longitude_actuelle = serializers.SerializerMethodField()
    derniere_mise_a_jour = serializers.SerializerMethodField()
    heure_derniere_mise_a_jour = serializers.SerializerMethodField()
    lien_historique = serializers.SerializerMethodField()
    
    class Meta:
        model = PathTemplate
        fields = [
            'id', 'nom_trajet', 'objet_nom', 'capteur_num_serie', 
            'etat_objet', 'localisation_actuelle', 'latitude_actuelle', 
            'longitude_actuelle', 'derniere_mise_a_jour', 
            'heure_derniere_mise_a_jour', 'lien_historique'
        ]
    
    def get_objet_nom(self, obj):
        """Nom de l'objet associé au trajet"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.object_tracking:
            return f"{messeur.object_tracking.categorie}_{messeur.object_tracking.capture_RFID.num_serie}"
        return "Non assigné"
    
    def get_capteur_num_serie(self, obj):
        """Numéro de série du capteur RFID"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.capture_rfid:
            return messeur.capture_rfid.num_serie
        return "N/A"
    
    def get_etat_objet(self, obj):
        """État actuel de l'objet avec logique intelligente"""
        from datetime import datetime, timedelta
        import math
        
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.object_tracking:
            objet = messeur.object_tracking
            
            # Vérifier si l'objet est perdu (pas de mise à jour récente)
            if messeur.date_prevu and messeur.heure:
                last_update = datetime.combine(messeur.date_prevu, messeur.heure)
                time_diff = (datetime.now() - last_update).total_seconds()
                
                if time_diff >  172800:  # Plus de 2 heures sans signal
                    if objet.etat != 'perdu':
                        objet.etat = 'perdu'
                        objet.save()
                        return 'perdu'
            
            # Logique basée sur la position (simulation car pas de vraies coordonnées)
            # Dans un vrai système, on utiliserait les vraies coordonnées GPS
            if messeur.lieu == obj.source:
                if objet.etat != 'stocke':
                    objet.etat = 'stocke'
                    objet.save()
                return 'stocke'
            elif messeur.lieu == obj.destination:
                if objet.etat != 'reçu':
                    objet.etat = 'reçu'
                    objet.save()
                return 'reçu'
            else:
                if objet.etat not in ['en_transit', 'perdu']:
                    objet.etat = 'en_transit'
                    objet.save()
                return 'en_transit'
            
            return objet.etat
        return "Inconnu"
    
    def get_localisation_actuelle(self, obj):
        """Localisation textuelle actuelle de l'objet"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur:
            # Pour simulation temps réel, utiliser le lieu du MesseurTracking
            return messeur.lieu
        return "Position inconnue"
    
    def get_latitude_actuelle(self, obj):
        """Latitude actuelle - simulation temps réel"""
        import random
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur:
            # Simulation: variation autour de la latitude source
            base_lat = obj.latitude_src
            # Petite variation pour simuler le mouvement (+/- 0.01 degrés)
            variation = (random.random() - 0.5) * 0.02
            return round(base_lat + variation, 6)
        return None
    
    def get_longitude_actuelle(self, obj):
        """Longitude actuelle - simulation temps réel"""
        import random
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur:
            # Simulation: variation autour de la longitude source
            base_lng = obj.longitude_src
            # Petite variation pour simuler le mouvement (+/- 0.01 degrés)
            variation = (random.random() - 0.5) * 0.02
            return round(base_lng + variation, 6)
        return None
    
    def get_derniere_mise_a_jour(self, obj):
        """Date de la dernière mise à jour depuis MesseurTracking.date_prevu"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.date_prevu:
            return messeur.date_prevu.isoformat()
        
        # Fallback: date actuelle si pas de MesseurTracking
        from datetime import date
        return date.today().isoformat()
    
    def get_heure_derniere_mise_a_jour(self, obj):
        """Heure de la dernière mise à jour depuis MesseurTracking.heure"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.heure:
            return messeur.heure.strftime("%H:%M:%S")
        
        # Fallback: heure actuelle si pas de MesseurTracking
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def get_lien_historique(self, obj):
        """Lien pour voir l'historique du trajet"""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/captures/trajet-historique/{obj.id}/')
        return f'/api/captures/trajet-historique/{obj.id}/'
'''
class TrajetListSerializer(serializers.ModelSerializer):
    """
    Serializer pour lister tous les trajets avec informations temps réel
    """
    nom_trajet = serializers.CharField(source='nom')
    objet_nom = serializers.SerializerMethodField()
    capteur_num_serie = serializers.SerializerMethodField()
    etat_objet = serializers.SerializerMethodField()
    localisation_actuelle = serializers.SerializerMethodField()
    latitude_actuelle = serializers.SerializerMethodField()
    longitude_actuelle = serializers.SerializerMethodField()
    derniere_mise_a_jour = serializers.SerializerMethodField()
    heure_derniere_mise_a_jour = serializers.SerializerMethodField()
    lien_historique = serializers.SerializerMethodField()
    
    class Meta:
        model = PathTemplate
        fields = [
            'id', 'nom_trajet', 'objet_nom', 'capteur_num_serie', 
            'etat_objet', 'localisation_actuelle', 'latitude_actuelle', 
            'longitude_actuelle', 'derniere_mise_a_jour', 
            'heure_derniere_mise_a_jour', 'lien_historique'
        ]
    
    def get_objet_nom(self, obj):
        """Nom de l'objet associé au trajet"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.object_tracking:
            return f"{messeur.object_tracking.categorie}_{messeur.object_tracking.capture_RFID.num_serie}"
        return "Non assigné"
    
    def get_capteur_num_serie(self, obj):
        """Numéro de série du capteur RFID"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.capture_rfid:
            return messeur.capture_rfid.num_serie
        return "N/A"
    
    def get_etat_objet(self, obj):
        """État actuel de l'objet avec la même logique que TrajetHistoriqueView"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if not messeur:
            return "Inconnu"
        
        # Utiliser la même logique que dans TrajetHistoriqueView
        return self._determiner_etat_objet(messeur, obj)
    
    def _determiner_etat_objet(self, messeur, path_template):
        """
        Détermine l'état dynamique de l'objet selon sa position dans le trajet
        MÊME LOGIQUE que dans TrajetHistoriqueView
        
        Logique:
        - "recu" : Si l'objet est à la destination finale (PRIORITÉ ABSOLUE)
        - "en_transit" : Si l'objet est entre le départ et la destination
        - "stocke" : Si l'objet est dans un point intermédiaire et y reste
        """
        from datetime import datetime, timedelta
        from django.db import models
        
        # ============================================================================
        # PRIORITÉ 1: Si l'objet est à la destination finale -> TOUJOURS "recu"
        # ============================================================================
        if messeur.lieu and path_template.destination:
            lieu_destination = path_template.destination.lower()
            lieu_actuel = messeur.lieu.lower()
            
            # Correspondance exacte
            if lieu_destination == lieu_actuel:
                return "recu"
            
            # Correspondance partielle (ex: "Béjaïa Port" dans "Béjaïa Port, Béjaïa")
            destination_mots = lieu_destination.split()
            for mot in destination_mots:
                if len(mot) > 3 and mot in lieu_actuel:  # Mots significatifs seulement
                    return "recu"
            
            # Correspondance inverse (ex: "Béjaïa" dans "Béjaïa Port")
            actuel_mots = lieu_actuel.split()
            for mot in actuel_mots:
                if len(mot) > 3 and mot in lieu_destination:
                    return "recu"
        
        # ============================================================================
        # Vérifier aussi dans l'historique si l'objet est arrivé à destination
        # ============================================================================
        if path_template.destination:
            destination_atteinte = PositionHistorique.objects.filter(
                messeur_tracking=messeur,
                lieu__icontains=path_template.destination.split(',')[0] if ',' in path_template.destination else path_template.destination.split()[0]
            ).exists()
            
            if destination_atteinte:
                return "recu"
        
        # ============================================================================
        # PRIORITÉ 2: Si l'objet est au point de départ
        # ============================================================================
        if messeur.lieu == path_template.source:
            # Vérifier s'il y a des positions dans l'historique après le départ
            positions_apres_depart = PositionHistorique.objects.filter(
                messeur_tracking=messeur
            ).exclude(lieu=path_template.source).exists()
            
            if positions_apres_depart:
                return "en_transit"  # Il a bougé puis est revenu
            else:
                return "stocke"  # Il n'a pas encore commencé
        
        # ============================================================================
        # PRIORITÉ 3: Si l'objet est dans un point intermédiaire
        # ============================================================================
        # Récupérer les points du trajet pour vérification
        path_points = PathTemplatePoint.objects.filter(
            template=path_template
        ).select_related('point')
        
        for path_point in path_points:
            if messeur.lieu and path_point.point.nom_lieu:
                if (path_point.point.nom_lieu in messeur.lieu or 
                    messeur.lieu in path_point.point.nom_lieu):
                    
                    # Vérifier depuis combien de temps il est dans ce lieu
                    derniere_position = PositionHistorique.objects.filter(
                        messeur_tracking=messeur,
                        lieu=messeur.lieu
                    ).order_by('-timestamp').first()
                    
                    if derniere_position and derniere_position.date_entree:
                        # Si il est dans ce lieu depuis plus d'une journée, considérer comme stocké
                        temps_dans_lieu = datetime.now() - derniere_position.date_entree.replace(tzinfo=None)
                        
                        if temps_dans_lieu > timedelta(hours=24):
                            return "stocke"
                        else:
                            return "en_transit"
                    
                    return "en_transit"
        
        # ============================================================================
        # Vérifier si l'objet est perdu (pas de mise à jour récente)
        # ============================================================================
        if messeur.date_prevu and messeur.heure:
            last_update = datetime.combine(messeur.date_prevu, messeur.heure)
            time_diff = (datetime.now() - last_update).total_seconds()
            
            if time_diff > 172800:  # Plus de 48 heures sans signal
                return 'perdu'
        
        # ============================================================================
        # Par défaut, si l'objet est quelque part entre les points
        # ============================================================================
        return "en_transit"
    
    def get_localisation_actuelle(self, obj):
        """Localisation textuelle actuelle de l'objet"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur:
            return messeur.lieu
        return "Position inconnue"
    
    def get_latitude_actuelle(self, obj):
        """Latitude actuelle depuis PositionHistorique ou simulation"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur:
            # Obtenir la dernière position depuis PositionHistorique
            derniere_position = PositionHistorique.objects.filter(
                messeur_tracking=messeur
            ).order_by('-timestamp').first()
            
            if derniere_position and derniere_position.latitude:
                return derniere_position.latitude
            
            # Fallback: simulation autour de la latitude source
            import random
            if obj.latitude_src:
                base_lat = obj.latitude_src
                variation = (random.random() - 0.5) * 0.02
                return round(base_lat + variation, 6)
        return None
    
    def get_longitude_actuelle(self, obj):
        """Longitude actuelle depuis PositionHistorique ou simulation"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur:
            # Obtenir la dernière position depuis PositionHistorique
            derniere_position = PositionHistorique.objects.filter(
                messeur_tracking=messeur
            ).order_by('-timestamp').first()
            
            if derniere_position and derniere_position.longitude:
                return derniere_position.longitude
            
            # Fallback: simulation autour de la longitude source
            import random
            if obj.longitude_src:
                base_lng = obj.longitude_src
                variation = (random.random() - 0.5) * 0.02
                return round(base_lng + variation, 6)
        return None
    
    def get_derniere_mise_a_jour(self, obj):
        """Date de la dernière mise à jour depuis MesseurTracking.date_prevu"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.date_prevu:
            return messeur.date_prevu.isoformat()
        
        # Fallback: date actuelle si pas de MesseurTracking
        from datetime import date
        return date.today().isoformat()
    
    def get_heure_derniere_mise_a_jour(self, obj):
        """Heure de la dernière mise à jour depuis MesseurTracking.heure"""
        messeur = MesseurTracking.objects.filter(path=obj).first()
        if messeur and messeur.heure:
            return messeur.heure.strftime("%H:%M:%S")
        
        # Fallback: heure actuelle si pas de MesseurTracking
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def get_lien_historique(self, obj):
        """Lien pour voir l'historique du trajet"""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/captures/trajet-historique/{obj.id}/')
        return f'/api/captures/trajet-historique/{obj.id}/'
        fields = ['site' ,'num_serie' , 'type' ,'date_install' ,'ObjectTracking','categorie']

    def create(self, validated_data):
        categorie = validated_data.pop("categorie")
        tag_rfid = TagRfid.objects.create(**validated_data)

        ## creat the object traking linked to the tagrfid 
        ObjectTracking.objects.create(
            site=tag_rfid.site, 
            capture_RFID=tag_rfid, 
            categorie=categorie,
            etat= "stocké"
        )
        return tag_rfid



class TagRfidListSerializer(serializers.ModelSerializer) : 
    class Meta : 
        model=  TagRfid
        fields = '__all__'


class RealtimeParametreSerializer(serializers.ModelSerializer):
    nom = serializers.CharField(source='typeParametre.nom')
    unite = serializers.CharField(source='typeParametre.unite')
    valeur_max = serializers.DecimalField(source='typeParametre.valeur_max', max_digits=10, decimal_places=2)

    class Meta:
        model = SiteParametre
        fields = ['nom', 'unite', 'valeur_max', 'valeur', 'date_heure']
