from django.shortcuts import render
from rest_framework.exceptions import ValidationError , NotFound
from django_tenants.utils import schema_context
from django.shortcuts import render
from rest_framework import generics , status
from sites.models import Site
import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
import time  
from .serializers import (TagRfidSerializer, PlanifierTrajetSerializer, 
                         TrackingPointSerializer, ObjectTrackingSerializer, 
                         PathTemplateSerializer, TrajetListSerializer)
from rest_framework import generics
from tenants.models import Client
from .services import GeolocationService
from django.http import StreamingHttpResponse
import json
import math
from django.core.cache import cache
from datetime import datetime, timedelta
from .models import MesseurTracking
from .models import PathTemplate, PathTemplatePoint, MesseurTracking ,TagRfid , TrackingPoint, ObjectTracking ,PositionHistorique
from datetime import datetime, timedelta
import random
from django.utils import timezone
from django.db import models
import pytz
from datetime import datetime, timedelta, time as datetime_time , date 

              

class CreateTagRfidView (generics.CreateAPIView) : 
    serializer_class = TagRfidSerializer

    def get_schema_name(self):
        client_id = self.request.query_params.get('client_id')
        if not client_id:
            raise ValidationError("client id is required")
        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            raise NotFound("client with this id not found")
        return client.schema_name

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['schema_name'] = self.get_schema_name()
        return context

    def create(self, request, *args, **kwargs):
        schema_name = self.get_schema_name()
        with schema_context(schema_name):
            return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        site = serializer.validated_data['site']
        if not site.asset_tracking:
            site.asset_tracking = True
            site.save()
        serializer.save()
    


class UploadTagRfidUserView(APIView):
    """
    Upload an Excel file with multiple tag rfids.
    File should have columns: num_serie, date_install, type (passif , actif)
    """

    def post(self, request, format=None):
        client_id = request.query_params.get("client_id")
        if not client_id : 
            raise ValidationError("client id is required ")
        
        try : 
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist : 
            raise NotFound("client with this id not found ")
        
        file = request.FILES.get('file')
        site_id = request.data.get('site')
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        if not site_id:
            return Response({"error": "No site ID provided"}, status=status.HTTP_400_BAD_REQUEST)
        try :
            df = pd.read_excel(file)
            # Convert rows to list of dicts
            tags_data = df.to_dict(orient='records')
        except Exception as e:
            return Response({"error": f"Invalid file format: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        created_tags = []
        errors = []
        required_columns = ['date_install', 'type', 'num_serie' ]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return Response(
                {"error": f"Missing required columns: {', '.join(missing_columns)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with schema_context(client.schema_name):
            try:
                site = Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                return Response({"error": "Site not found"}, status=status.HTTP_404_NOT_FOUND)

            for i, tag_data in enumerate(tags_data):
                tag_data['site'] = site.id
                # fix date format if needed
                if isinstance(tag_data.get('date_install'), pd.Timestamp):
                    tag_data['date_install'] = tag_data['date_install'].date()
                for key in ['type', 'num_serie']:
                    if tag_data.get(key):
                        tag_data[key] = str(tag_data[key]).strip()
                        
                serializer = TagRfidSerializer(data=tag_data)
                if serializer.is_valid():
                    serializer.save()
                    created_tags.append(serializer.data)
                else:
                    errors.append({"row": i+1, "errors": serializer.errors})

            if created_tags and not site.asset_tracking:
                site.asset_tracking = True
                site.save()

        if errors:
            return Response({"created": created_tags, "errors": errors}, status=status.HTTP_207_MULTI_STATUS)
        return Response({"created": created_tags}, status=status.HTTP_201_CREATED)


# Nouvelles vues pour la planification de trajet
class TrackingPointListView(generics.ListAPIView):
    """
    API pour lister tous les points de tracking disponibles
    """
    serializer_class = TrackingPointSerializer
    
    def get_queryset(self):
        return TrackingPoint.objects.all()


class ObjectTrackingListView(generics.ListAPIView):
    """
    API pour lister tous les objets de tracking disponibles
    """
    serializer_class = ObjectTrackingSerializer
    
    def get_queryset(self):
        return ObjectTracking.objects.all()


class ObjectTrackingNamesView(APIView):
    """
    API pour lister tous les noms d'objets de tracking disponibles
    """
    
    def get(self, request, *args, **kwargs):
        objets = ObjectTracking.objects.select_related('capture_RFID').all()
        
        objets_list = []
        for obj in objets:
            nom_objet = f"{obj.categorie}_{obj.capture_RFID.num_serie}"
            objets_list.append({
                'id': obj.id,
                'nom_objet': nom_objet,
                'categorie': obj.categorie,
                'num_serie': obj.capture_RFID.num_serie,
                'etat': obj.etat,
                'site_id': obj.site.id
            })
        
        return Response(objets_list)


'''class PlanifierTrajetView(APIView):
    """
    API pour planifier un nouveau trajet
    """
    
    def post(self, request, *args, **kwargs):
        serializer = PlanifierTrajetSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            
            response_data = {
                'message': 'Trajet planifié avec succès',
                'path_template': PathTemplateSerializer(result['path_template']).data,
                'messeur_tracking_id': result['messeur_tracking'].id
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

'''
class PlanifierTrajetView(APIView):
    """
    API pour planifier un nouveau trajet
    """
    
    def post(self, request, *args, **kwargs):
        serializer = PlanifierTrajetSerializer(data=request.data)
        if serializer.is_valid():
            # Récupérer l'objet à partir des données du serializer
            objet_tracking_nom = serializer.validated_data.get('objet_tracking_nom')
            
            try:
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
                    return Response({
                        'error': f'Objet tracking "{objet_tracking_nom}" non trouvé.'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # Vérifier l'état actuel de l'objet
                etat_actuel = objet_tracking.etat
                
                # Vérifier si l'objet a déjà un trajet actif
                trajet_actif = MesseurTracking.objects.filter(
                    object_tracking=objet_tracking
                ).order_by('-date_debut').first()
                
                if trajet_actif:
                    # Si l'objet n'est pas en état "reçu", empêcher la planification
                    if etat_actuel not in ['reçu', 'recu']:  # Gérer les deux orthographes
                        return Response({
                            'error': f'Impossible de planifier un nouveau trajet pour l\'objet "{objet_tracking_nom}".',
                            'raison': f'L\'objet est actuellement en état "{etat_actuel}" dans un trajet actif.',
                            'trajet_actif': {
                                'trajet_id': trajet_actif.path.id,
                                'nom_trajet': trajet_actif.path.nom,
                                'etat_objet': etat_actuel,
                                'source': trajet_actif.path.source,
                                'destination': trajet_actif.path.destination,
                                'date_debut': trajet_actif.date_debut.isoformat(),
                                'lieu_actuel': trajet_actif.lieu,
                                'date_derniere_maj': trajet_actif.date_prevu.isoformat() if trajet_actif.date_prevu else None,
                                'heure_derniere_maj': trajet_actif.heure.strftime('%H:%M:%S') if trajet_actif.heure else None
                            },
                            'etats_autorises': ['reçu', 'recu'],
                            'message_details': 'Veuillez attendre que l\'objet soit livré (état "reçu") avant de planifier un nouveau trajet.',
                            'suggestions': [
                                'Vérifiez l\'état actuel du trajet en cours',
                                'Attendez que l\'objet arrive à destination',
                                'Contactez l\'équipe de logistique si nécessaire'
                            ]
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Si l'objet est "reçu", procéder directement à la création du nouveau trajet
                # SUPPRESSION du warning et de la vérification de temps
                result = serializer.save()
                
                # Mettre à jour l'état de l'objet pour le nouveau trajet
                objet_tracking.etat = 'stocke'  # L'objet commence par être stocké au point de départ
                objet_tracking.save()
                
                response_data = {
                    'message': 'Trajet planifié avec succès',
                    'path_template': PathTemplateSerializer(result['path_template']).data,
                    'messeur_tracking_id': result['messeur_tracking'].id,
                    'objet_details': {
                        'nom_objet': objet_tracking_nom,
                        'etat_precedent': etat_actuel,
                        'nouvel_etat': 'stocke',
                        'nouveau_trajet_id': result['path_template'].id
                    },
                    'trajet_precedent': {
                        'trajet_id': trajet_actif.path.id if trajet_actif else None,
                        'nom_trajet': trajet_actif.path.nom if trajet_actif else None,
                        'etat_final': etat_actuel,
                        'lieu_final': trajet_actif.lieu if trajet_actif else None,
                        'date_fin': trajet_actif.date_prevu.isoformat() if trajet_actif and trajet_actif.date_prevu else None,
                        'heure_fin': trajet_actif.heure.strftime('%H:%M:%S') if trajet_actif and trajet_actif.heure else None
                    } if trajet_actif else None,
                    'statistiques': {
                        'nouveau_trajet_source': result['path_template'].source,
                        'nouveau_trajet_destination': result['path_template'].destination,
                        'transition': f'{etat_actuel} → stocke',
                        'planification_directe': True
                    }
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    'error': f'Erreur lors de la vérification de l\'objet: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


class PathTemplateListView(generics.ListAPIView):
    """
    API pour lister tous les templates de chemin
    """
    serializer_class = PathTemplateSerializer
    
    def get_queryset(self):
        return PathTemplate.objects.all()


class TrajetListView(generics.ListAPIView):
    """
    API pour lister tous les trajets avec données temps réel simulées
    GET /api/captures/liste-trajets/
    """
    serializer_class = TrajetListSerializer
    
    def get_queryset(self):
        # Vérifier les objets perdus avant de retourner la liste
        self.check_lost_objects()
        return PathTemplate.objects.select_related().all()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def check_lost_objects(self):
        """
        Vérifier et marquer les objets comme perdus si pas de signal depuis longtemps
        """
       
        
        # Objets sans signal depuis plus de 2 heures
        cutoff_time = datetime.now() - timedelta(hours=2)
        
        lost_messeurs = MesseurTracking.objects.filter(
            date_prevu__lt=cutoff_time.date()
        ).exclude(object_tracking__etat='perdu')
        
        for messeur in lost_messeurs:
            last_update = datetime.combine(messeur.date_prevu, messeur.heure)
            if last_update < cutoff_time:
                messeur.object_tracking.etat = 'perdu'
                messeur.object_tracking.save()







    def post(self, request):
        print(f"🎯 CLASSE UTILISÉE: {self.__class__.__name__}")
        
        tag_num_serie = request.data.get('tag_rfid_num_serie')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        timestamp = request.data.get('timestamp')
        
        print(f"DEBUG - Données reçues:")
        print(f"   Tag: {tag_num_serie}")
        print(f"   Coordonnées: {latitude}, {longitude}")
        print(f"   Timestamp brut: {timestamp}")
        
        if not all([tag_num_serie, latitude, longitude, timestamp]):
            return Response({
                'error': 'tag_rfid_num_serie, latitude, longitude ET timestamp sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Géolocalisation inverse automatique pour déterminer le lieu
        lieu = self.get_location_from_coordinates(latitude, longitude)
        
        try:
            # Trouver le tag RFID
            tag_rfid = TagRfid.objects.get(num_serie=tag_num_serie)
            
            # Trouver le MesseurTracking actif
            messeur = MesseurTracking.objects.filter(
                capture_rfid=tag_rfid
            ).order_by('-date_debut').first()
            
            if not messeur:
                return Response({
                    'error': f'Aucun trajet actif pour le tag {tag_num_serie}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Sauvegarder l'ancienne position actuelle AVANT de la modifier
            previous_lieu = messeur.lieu
            previous_latitude, previous_longitude = self.get_current_coordinates(messeur)
            
            # ====================================================================
            # TRAITEMENT TIMESTAMP - VERSION ULTRA SIMPLE
            # ====================================================================
            try:
                # Nettoyer le timestamp
                timestamp_clean = timestamp.strip()
                timestamp_clean = timestamp_clean.replace('Z', '')
                timestamp_clean = timestamp_clean.replace('+00:00', '')
                timestamp_clean = timestamp_clean.replace('T', ' ')
                
                print(f"Timestamp nettoyé: '{timestamp_clean}'")
                
                # Format attendu: "YYYY-MM-DD HH:MM:SS"
                if ' ' not in timestamp_clean:
                    return Response({
                        'error': 'Format timestamp invalide. Format requis: YYYY-MM-DD HH:MM:SS',
                        'timestamp_recu': timestamp
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                date_str, time_str = timestamp_clean.split(' ', 1)
                
                # ================================================================
                # PARSER LA DATE - SIMPLE
                # ================================================================
                try:
                    year, month, day = map(int, date_str.split('-'))
                    new_date = date(year, month, day)
                    print(f"✅ Date créée: {new_date}")
                except ValueError as e:
                    return Response({
                        'error': f'Date invalide: {date_str} - {str(e)}',
                        'format_requis': 'YYYY-MM-DD'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # ================================================================
                # PARSER L'HEURE - SIMPLE SANS CONVERSION
                # ================================================================
                try:
                    time_parts = time_str.split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                    second = int(float(time_parts[2])) if len(time_parts) > 2 else 0
                    
                    print(f"Composants heure: {hour}h {minute}m {second}s")
                    
                    # VALIDATION STRICTE
                    if not (0 <= hour <= 23):
                        raise ValueError(f"Heure invalide: {hour} (doit être entre 0 et 23)")
                    if not (0 <= minute <= 59):
                        raise ValueError(f"Minutes invalides: {minute}")
                    if not (0 <= second <= 59):
                        raise ValueError(f"Secondes invalides: {second}")
                    
                    # ============================================================
                    # CRÉER L'HEURE SOUS FORME DE STRING POUR ÉVITER CONVERSIONS
                    # ============================================================
                    new_heure_str = f"{hour:02d}:{minute:02d}:{second:02d}"
                    print(f"✅ Heure en string: {new_heure_str}")
                    
                except ValueError as e:
                    return Response({
                        'error': f'Heure invalide: {time_str} - {str(e)}',
                        'format_requis': 'HH:MM:SS'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # ================================================================
                # CRÉER DATETIME POUR HISTORIQUE SEULEMENT
                # ================================================================
                new_datetime_simple = datetime.combine(new_date, datetime_time(hour, minute, second))
                
                # Le rendre timezone-aware avec UTC par défaut
                from django.utils import timezone as django_timezone
                new_datetime = django_timezone.make_aware(new_datetime_simple, timezone=django_timezone.utc)
                
                print(f"✅ DateTime final: {new_datetime}")
                
            except Exception as e:
                print(f"❌ Erreur parsing: {str(e)}")
                return Response({
                    'error': f'Erreur parsing timestamp: {str(e)}',
                    'timestamp_recu': timestamp,
                    'format_requis': 'YYYY-MM-DD HH:MM:SS'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ====================================================================
            # LOGIQUE HISTORIQUE ET ÉTAT DE L'OBJET
            # ====================================================================
            
            # ÉTAPE 1: SAUVEGARDER L'ANCIENNE POSITION
            if messeur.lieu and messeur.date_prevu and messeur.heure:
                try:
                    if isinstance(messeur.heure, str):
                        hour_parts = messeur.heure.split(':')
                        old_hour = int(hour_parts[0])
                        old_minute = int(hour_parts[1])
                        old_second = int(hour_parts[2]) if len(hour_parts) > 2 else 0
                        old_time = datetime_time(old_hour, old_minute, old_second)
                    else:
                        old_time = messeur.heure
                    
                    ancienne_datetime_simple = datetime.combine(messeur.date_prevu, old_time)
                    ancienne_datetime = django_timezone.make_aware(ancienne_datetime_simple, timezone=django_timezone.utc)
                except Exception as e:
                    print(f"Erreur ancienne datetime: {e}")
                    ancienne_datetime = new_datetime
                
                ancienne_position = PositionHistorique.objects.create(
                    messeur_tracking=messeur,
                    lieu=messeur.lieu,
                    latitude=previous_latitude if previous_latitude else 0.0,
                    longitude=previous_longitude if previous_longitude else 0.0,
                    timestamp=ancienne_datetime,
                    date_sortie=new_datetime
                )
                
                if previous_lieu != lieu:
                    premiere_entree_ancien_lieu = PositionHistorique.objects.filter(
                        messeur_tracking=messeur,
                        lieu=previous_lieu,
                        date_entree__isnull=False
                    ).order_by('timestamp').first()
                    
                    if premiere_entree_ancien_lieu and premiere_entree_ancien_lieu.date_entree:
                        duree_dans_ancien_lieu = new_datetime - premiere_entree_ancien_lieu.date_entree
                        ancienne_position.duree_dans_lieu = duree_dans_ancien_lieu
                        ancienne_position.date_entree = premiere_entree_ancien_lieu.date_entree
                        ancienne_position.save()
            
            # ÉTAPE 2: CRÉER L'ENTRÉE POUR LA NOUVELLE POSITION
            nouvelle_position = PositionHistorique.objects.create(
                messeur_tracking=messeur,
                lieu=lieu,
                latitude=float(latitude),
                longitude=float(longitude),
                timestamp=new_datetime,
                date_entree=new_datetime
            )
            
            # ====================================================================
            # ÉTAPE 3: CALCULER LA DURÉE DE PASSAGE - CORRECTION POUR DURÉE RÉELLE
            # ====================================================================
            if previous_lieu == lieu:
                # L'objet est toujours dans le même lieu
                premiere_entree = PositionHistorique.objects.filter(
                    messeur_tracking=messeur,
                    lieu=lieu,
                    date_entree__isnull=False
                ).order_by('timestamp').first()
                
                if premiere_entree and premiere_entree.date_entree:
                    # ✅ CALCUL DE LA VRAIE DURÉE : nouveau temps - première entrée
                    duree_dans_lieu = new_datetime - premiere_entree.date_entree
                    
                    # Obtenir le nombre total de secondes
                    total_seconds = int(duree_dans_lieu.total_seconds())
                    
                    # ✅ PAS DE LIMITATION - CALCULER LA VRAIE DURÉE
                    if total_seconds < 0:
                        # Si la durée est négative, réinitialiser
                        messeur.duree_passage = "00:00:00"
                        print("⚠️ Durée négative détectée, réinitialisée à 00:00:00")
                    else:
                        # Calculer heures, minutes, secondes SANS limitation
                        heures = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        secondes = total_seconds % 60
                        
                        # ✅ AUTORISER LES DURÉES > 24H (ex: 25:30:45, 100:15:30, etc.)
                        messeur.duree_passage = f"{heures:02d}:{minutes:02d}:{secondes:02d}"
                        print(f"✅ Durée réelle calculée: {messeur.duree_passage} ({total_seconds} secondes total)")
                else:
                    messeur.duree_passage = "00:00:00"
            else:
                # L'objet a changé de lieu - commencer un nouveau compteur
                messeur.duree_passage = "00:00:00"
                print("🔄 Changement de lieu détecté - durée réinitialisée")
            
            # LOGIQUE ÉTAT DE L'OBJET
            objet = messeur.object_tracking
            path = messeur.path
            
            def calculate_distance(lat1, lon1, lat2, lon2):
                R = 6371
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                return R * c * 1000
            
            distance_source = calculate_distance(
                float(latitude), float(longitude),
                path.latitude_src, path.longitude_src
            )
            
            distance_destination = calculate_distance(
                float(latitude), float(longitude),
                path.latitude_dest, path.longitude_dest
            )
            
            if distance_source <= 100:
                if objet.etat != 'stocke':
                    objet.etat = 'stocke'
                    objet.save()
            elif distance_destination <= 100:
                if objet.etat != 'reçu':
                    objet.etat = 'reçu'
                    objet.save()
            else:
                if objet.etat != 'en_transit':
                    objet.etat = 'en_transit'
                    objet.save()
            
            # ====================================================================
            # SAUVEGARDE AVEC GESTION INTELLIGENTE DES DURÉES > 24H
            # ====================================================================
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    duree_str = str(messeur.duree_passage) if messeur.duree_passage else "00:00:00"
                    
                    # ✅ VALIDATION ET GESTION DES DURÉES > 24H
                    duree_parts = duree_str.split(':')
                    if len(duree_parts) == 3:
                        heures_int = int(duree_parts[0])
                        
                        if heures_int >= 24:
                            # PostgreSQL TIME ne supporte pas > 23:59:59
                            print(f"⚠️  Durée > 24h détectée: {duree_str}")
                            
                            # Convertir en format descriptif pour les notes
                            jours = heures_int // 24
                            heures_restantes = heures_int % 24
                            
                            duree_descriptive = f"{jours}j {heures_restantes:02d}:{duree_parts[1]}:{duree_parts[2]}"
                            print(f"✅ Format descriptif: {duree_descriptive}")
                            
                            # Pour la base de données, utiliser la durée modulo 24h + note
                            duree_pour_db = f"{heures_restantes:02d}:{duree_parts[1]}:{duree_parts[2]}"
                            
                            # ✅ VÉRIFIER SI LA COLONNE 'notes' EXISTE
                            cursor.execute("""
                                SELECT column_name FROM information_schema.columns 
                                WHERE table_name = 'captures_messeurtracking' AND column_name = 'notes'
                            """)
                            notes_column_exists = cursor.fetchone() is not None
                            
                            if notes_column_exists:
                                # Avec notes
                                cursor.execute("""
                                    UPDATE captures_messeurtracking 
                                    SET lieu = %s, date_prevu = %s, heure = %s, 
                                        duree_passage = %s,
                                        notes = CONCAT(COALESCE(notes, ''), ' [Durée totale: ', %s, ']')
                                    WHERE id = %s
                                """, [
                                    lieu, 
                                    new_date.strftime('%Y-%m-%d'), 
                                    new_heure_str,
                                    duree_pour_db,  # TIME valide
                                    duree_descriptive,  # Durée complète en note
                                    messeur.id
                                ])
                            else:
                                # Sans notes - juste la durée limitée
                                cursor.execute("""
                                    UPDATE captures_messeurtracking 
                                    SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                                    WHERE id = %s
                                """, [
                                    lieu, 
                                    new_date.strftime('%Y-%m-%d'), 
                                    new_heure_str,
                                    duree_pour_db,
                                    messeur.id
                                ])
                                
                            # Stocker la vraie durée pour la réponse
                            duree_response = duree_descriptive
                        else:
                            # Durée normale < 24h
                            cursor.execute("""
                                UPDATE captures_messeurtracking 
                                SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                                WHERE id = %s
                            """, [
                                lieu, 
                                new_date.strftime('%Y-%m-%d'), 
                                new_heure_str,
                                duree_str,
                                messeur.id
                            ])
                            duree_response = duree_str
                    else:
                        # Format invalide
                        duree_str = "00:00:00"
                        duree_response = duree_str
                        cursor.execute("""
                            UPDATE captures_messeurtracking 
                            SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                            WHERE id = %s
                        """, [
                            lieu, 
                            new_date.strftime('%Y-%m-%d'), 
                            new_heure_str,
                            duree_str,
                            messeur.id
                        ])

                print(f"✅ Sauvegarde avec durée réelle: {duree_response if 'duree_response' in locals() else duree_str}")
                
                # Recharger l'objet
                messeur.refresh_from_db()
                
            except Exception as sql_error:
                print(f"❌ Erreur raw SQL: {sql_error}")
                return Response({
                    'error': f'Erreur sauvegarde SQL: {str(sql_error)}',
                    'debug': {
                        'duree_calculee': duree_str if 'duree_str' in locals() else "N/A",
                        'total_seconds': total_seconds if 'total_seconds' in locals() else 0
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # ENVOYER MISE À JOUR SSE
            update_data = {
                'type': 'position_update',
                'trajet_id': messeur.path.id,
                'tag_rfid': tag_num_serie,
                'objet_nom': f"{messeur.object_tracking.categorie}_{tag_num_serie}",
                'etat_objet': objet.etat,
                'etat_change': previous_lieu != lieu,
                'distances': {
                    'source': round(distance_source, 2),
                    'destination': round(distance_destination, 2)
                },
                'nouvelle_position': {
                    'lieu': lieu,
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': new_date.isoformat(),
                    'heure': new_heure_str,
                    'duree_passage': duree_response if 'duree_response' in locals() else str(messeur.duree_passage)
                }
            }
            
            self.broadcast_sse_update(update_data)
            
            return Response({
                'success': True,
                'message': f'Position mise à jour pour {tag_num_serie}',
                'trajet_id': messeur.path.id,
                'etat_objet': objet.etat,
                'duree_passage': duree_response if 'duree_response' in locals() else str(messeur.duree_passage),
                'distances': update_data['distances'],
                'nouvelle_position': update_data['nouvelle_position'],
                'debug_info': {
                    'timestamp_recu': timestamp,
                    'date_finale': new_date.isoformat(),
                    'heure_finale_string': new_heure_str,
                    'duree_finale_reelle': duree_response if 'duree_response' in locals() else str(messeur.duree_passage),
                    'methode': 'Calcul durée réelle sans limitation'
                }
            })
            
        except TagRfid.DoesNotExist:
            return Response({
                'error': f'Tag RFID {tag_num_serie} non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"ERREUR GÉNÉRALE: {str(e)}")
            return Response({
                'error': f'Erreur: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_current_coordinates(self, messeur):
        """
        Obtenir les coordonnées GPS actuelles du MesseurTracking
        """
        # Essayer d'obtenir les coordonnées depuis les champs directs
        if hasattr(messeur, 'latitude') and hasattr(messeur, 'longitude'):
            if messeur.latitude and messeur.longitude:
                return float(messeur.latitude), float(messeur.longitude)
        
        # Sinon, essayer d'obtenir depuis la dernière position dans l'historique
        derniere_position = PositionHistorique.objects.filter(
            messeur_tracking=messeur
        ).order_by('-timestamp').first()
        
        if derniere_position and derniere_position.latitude and derniere_position.longitude:
            return float(derniere_position.latitude), float(derniere_position.longitude)
        
        # Par défaut, retourner None si pas de coordonnées
        return None, None
    
    def get_location_from_coordinates(self, latitude, longitude):
        """
        Obtenir le nom du lieu à partir des coordonnées GPS en utilisant la géolocalisation inverse
        """
        if not latitude or not longitude:
            return 'Position GPS inconnue'
        
        try:
            geolocation_service = GeolocationService()
            result = geolocation_service.geocoder.reverse_geocode(
                float(latitude), float(longitude)
            )
            
            # Extraire le nom du lieu principal à partir des composants d'adresse
            if result and 'address_components' in result:
                address = result['address_components']
                
                # Prioriser ville > commune > village > quartier
                lieu_parts = []
                
                if 'city' in address:
                    lieu_parts.append(address['city'])
                elif 'town' in address:
                    lieu_parts.append(address['town'])
                elif 'village' in address:
                    lieu_parts.append(address['village'])
                elif 'suburb' in address:
                    lieu_parts.append(address['suburb'])
                elif 'municipality' in address:
                    lieu_parts.append(address['municipality'])
                
                if 'state' in address and len(lieu_parts) > 0:
                    lieu_parts.append(address['state'])
                
                if lieu_parts:
                    lieu = ', '.join(lieu_parts)
                else:
                    # Utiliser le nom formaté et prendre les premiers éléments
                    formatted_address = result.get('formatted_address', '')
                    address_parts = formatted_address.split(',')
                    if len(address_parts) >= 2:
                        lieu = f"{address_parts[0].strip()}, {address_parts[1].strip()}"
                    else:
                        lieu = address_parts[0].strip() if address_parts else f"GPS({latitude}, {longitude})"
                        
                return lieu if lieu else f"GPS({latitude}, {longitude})"
            else:
                return f"GPS({latitude}, {longitude})"
                
        except Exception as e:
            # En cas d'erreur, utiliser les coordonnées
            print(f"Erreur géolocalisation: {str(e)}")
            return f"GPS({latitude}, {longitude})"
    
    def broadcast_sse_update(self, data):
        """
        Fonction pour broadcaster les mises à jour SSE
        """
        # Stocker la mise à jour dans le cache pour les clients SSE
        cache_key = f"sse_update_{data['trajet_id']}"
        cache.set(cache_key, json.dumps(data), 300)  # 5 minutes
        
        # Stocker aussi pour tous les trajets
        cache.set("sse_update_all", json.dumps(data), 300)


    """
    API pour recevoir les mises à jour de position temps réel des tags RFID
    POST /api/captures/update-position-realtime/
    """
    
    def post(self, request):
        tag_num_serie = request.data.get('tag_rfid_num_serie')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        timestamp_str = request.data.get('timestamp')
        
        print(f"DEBUG - Données reçues:")
        print(f"   Tag: {tag_num_serie}")
        print(f"   Coordonnées: {latitude}, {longitude}")
        print(f"   Timestamp brut: {timestamp_str}")
        
        if not all([tag_num_serie, latitude, longitude]):
            return Response({
                'error': 'tag_rfid_num_serie, latitude et longitude sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # CORRECTION COMPLÈTE du parsing timestamp
        try:
           
            if timestamp_str:
                # Nettoyer le timestamp
                if timestamp_str.endswith('Z'):
                    timestamp_clean = timestamp_str[:-1] + '+00:00'
                else:
                    timestamp_clean = timestamp_str
                
                print(f"Timestamp nettoyé: {timestamp_clean}")
                
                # Parser le timestamp UTC
                timestamp_utc = datetime.fromisoformat(timestamp_clean)
                print(f"Timestamp UTC parsé: {timestamp_utc}")
                
                # S'assurer qu'il est en UTC
                if timestamp_utc.tzinfo is None:
                    timestamp_utc = pytz.UTC.localize(timestamp_utc)
                
                # Convertir en heure d'Algérie (UTC+1)
                algerie_tz = pytz.timezone('Africa/Algiers')
                timestamp_local = timestamp_utc.astimezone(algerie_tz)
                print(f"Timestamp local Algérie: {timestamp_local}")
                
                # EXTRACTION SÉCURISÉE de la date et heure
                new_date = timestamp_local.date()
                raw_time = timestamp_local.time()
                
                print(f"Date extraite: {new_date}")
                print(f"Heure brute: {raw_time}")
                print(f"Composants heure: {raw_time.hour}h {raw_time.minute}m {raw_time.second}s")
                
                # VALIDATION ET CORRECTION si nécessaire
                if raw_time.hour >= 24:
                    print(f"PROBLÈME: Heure >= 24 détectée: {raw_time.hour}")
                    # Corriger l'heure
                    corrected_hour = raw_time.hour % 24
                    days_to_add = raw_time.hour // 24
                    
                    from datetime import time, timedelta
                    new_heure = time(corrected_hour, raw_time.minute, raw_time.second)
                    new_date = new_date + timedelta(days=days_to_add)
                    
                    print(f"Correction appliquée: {new_heure}, Date ajustée: {new_date}")
                else:
                    new_heure = raw_time
                    print(f"Heure valide: {new_heure}")
                
                # Reconstruire le datetime final
                new_datetime = datetime.combine(new_date, new_heure)
                new_datetime = algerie_tz.localize(new_datetime.replace(tzinfo=None))
                
            else:
                # Pas de timestamp fourni, utiliser l'heure actuelle
                print("Pas de timestamp fourni, utilisation heure actuelle")
                now = timezone.now()
                new_date = now.date()
                new_heure = now.time()
                new_datetime = now
                
        except Exception as e:
            print(f"ERREUR dans parsing timestamp: {str(e)}")
            print(f"   Type erreur: {type(e).__name__}")
            
            # Fallback sécurisé
            now = timezone.now()
            new_date = now.date()
            new_heure = now.time()
            new_datetime = now
            
            return Response({
                'error': f'Erreur parsing timestamp: {str(e)}',
                'timestamp_recu': timestamp_str,
                'fallback_utilise': new_datetime.isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Géolocalisation inverse automatique pour déterminer le lieu
        lieu = self.get_location_from_coordinates(latitude, longitude)
        
        try:
            # Trouver le tag RFID
            tag_rfid = TagRfid.objects.get(num_serie=tag_num_serie)
            
            # Trouver le MesseurTracking actif
            messeur = MesseurTracking.objects.filter(
                capture_rfid=tag_rfid
            ).order_by('-date_debut').first()
            
            if not messeur:
                return Response({
                    'error': f'Aucun trajet actif pour le tag {tag_num_serie}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Sauvegarder l'ancienne position actuelle AVANT de la modifier
            previous_lieu = messeur.lieu
            previous_latitude, previous_longitude = self.get_current_coordinates(messeur)
            
            # ÉTAPE 1: SAUVEGARDER L'ANCIENNE POSITION DANS L'HISTORIQUE
            if messeur.lieu and messeur.date_prevu and messeur.heure:
                try:
                    ancienne_datetime = datetime.combine(messeur.date_prevu, messeur.heure)
                    ancienne_datetime = timezone.make_aware(ancienne_datetime) if timezone.is_naive(ancienne_datetime) else ancienne_datetime
                except:
                    ancienne_datetime = new_datetime
                
                # Sauvegarder l'ancienne position dans l'historique
                ancienne_position = PositionHistorique.objects.create(
                    messeur_tracking=messeur,
                    lieu=messeur.lieu,
                    latitude=previous_latitude if previous_latitude else 0.0,
                    longitude=previous_longitude if previous_longitude else 0.0,
                    timestamp=ancienne_datetime,
                    date_sortie=new_datetime
                )
                
                # Si l'objet change de lieu, calculer la durée passée dans l'ancien lieu
                if previous_lieu != lieu:
                    premiere_entree_ancien_lieu = PositionHistorique.objects.filter(
                        messeur_tracking=messeur,
                        lieu=previous_lieu,
                        date_entree__isnull=False
                    ).order_by('timestamp').first()
                    
                    if premiere_entree_ancien_lieu and premiere_entree_ancien_lieu.date_entree:
                        duree_dans_ancien_lieu = new_datetime - premiere_entree_ancien_lieu.date_entree
                        ancienne_position.duree_dans_lieu = duree_dans_ancien_lieu
                        ancienne_position.date_entree = premiere_entree_ancien_lieu.date_entree
                        ancienne_position.save()
            
            # ÉTAPE 2: CRÉER L'ENTRÉE POUR LA NOUVELLE POSITION
            nouvelle_position = PositionHistorique.objects.create(
                messeur_tracking=messeur,
                lieu=lieu,
                latitude=float(latitude),
                longitude=float(longitude),
                timestamp=new_datetime,
                date_entree=new_datetime
            )
            
            # ÉTAPE 3: CALCULER LA DURÉE DE PASSAGE
            if previous_lieu == lieu:
                # L'objet est toujours dans le même lieu
                premiere_entree = PositionHistorique.objects.filter(
                    messeur_tracking=messeur,
                    lieu=lieu,
                    date_entree__isnull=False
                ).order_by('timestamp').first()
                
                if premiere_entree and premiere_entree.date_entree:
                    duree_dans_lieu = new_datetime - premiere_entree.date_entree
                    heures = int(duree_dans_lieu.total_seconds() // 3600)
                    minutes = int((duree_dans_lieu.total_seconds() % 3600) // 60)
                    secondes = int(duree_dans_lieu.total_seconds() % 60)
                    messeur.duree_passage = f"{heures:02d}:{minutes:02d}:{secondes:02d}"
                else:
                    messeur.duree_passage = "00:00:00"
            else:
                # L'objet a changé de lieu - commencer un nouveau compteur
                messeur.duree_passage = "00:00:00"
            
            # ÉTAPE 4: METTRE À JOUR MESSEURTRACKING AVEC LA NOUVELLE POSITION
            messeur.lieu = lieu
            messeur.date_prevu = new_date
            messeur.heure = new_heure
            
            # VALIDATION FINALE avant sauvegarde
            try:
                # Test de création d'un objet time pour vérifier la validité
                from datetime import time as time_class
                test_time = time_class(new_heure.hour, new_heure.minute, new_heure.second)
                print(f"Validation finale OK: {test_time}")
            except ValueError as ve:
                print(f"ERREUR validation finale: {ve}")
                return Response({
                    'error': f'Heure finale invalide: {ve}',
                    'heure_problematique': str(new_heure),
                    'timestamp_source': timestamp_str
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Ajouter les coordonnées GPS dans MesseurTracking si les champs existent
            if hasattr(messeur, 'latitude'):
                messeur.latitude = float(latitude)
            if hasattr(messeur, 'longitude'):
                messeur.longitude = float(longitude)
            
            # LOGIQUE INTELLIGENTE POUR L'ÉTAT DE L'OBJET
            objet = messeur.object_tracking
            path = messeur.path
            
            # Fonction pour calculer la distance entre deux points GPS
            def calculate_distance(lat1, lon1, lat2, lon2):
                R = 6371  # Rayon de la Terre en km
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                return R * c * 1000  # Distance en mètres
            
            # Distance par rapport à la source
            distance_source = calculate_distance(
                float(latitude), float(longitude),
                path.latitude_src, path.longitude_src
            )
            
            # Distance par rapport à la destination
            distance_destination = calculate_distance(
                float(latitude), float(longitude),
                path.latitude_dest, path.longitude_dest
            )
            
            # Logique de détermination de l'état
            if distance_source <= 100:  # Dans un rayon de 100m de la source
                if objet.etat != 'stocke':
                    objet.etat = 'stocke'
                    objet.save()
            elif distance_destination <= 100:  # Dans un rayon de 100m de la destination
                if objet.etat != 'reçu':
                    objet.etat = 'reçu'
                    objet.save()
            else:  # Entre source et destination - FORCE l'état en_transit car on reçoit un signal
                if objet.etat != 'en_transit':
                    objet.etat = 'en_transit'
                    objet.save()
            
            messeur.save()
            
            # ENVOYER MISE À JOUR SSE
            update_data = {
                'type': 'position_update',
                'trajet_id': messeur.path.id,
                'tag_rfid': tag_num_serie,
                'objet_nom': f"{messeur.object_tracking.categorie}_{tag_num_serie}",
                'etat_objet': objet.etat,
                'etat_change': previous_lieu != lieu,
                'distances': {
                    'source': round(distance_source, 2),
                    'destination': round(distance_destination, 2)
                },
                'nouvelle_position': {
                    'lieu': lieu,
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': new_date.isoformat(),
                    'heure': new_heure.strftime('%H:%M:%S'),
                    'duree_passage': str(messeur.duree_passage)
                }
            }
            
            # Broadcast à tous les clients SSE connectés
            self.broadcast_sse_update(update_data)
            
            return Response({
                'success': True,
                'message': f'Position mise à jour pour {tag_num_serie}',
                'trajet_id': messeur.path.id,
                'etat_objet': objet.etat,
                'duree_passage': str(messeur.duree_passage),
                'distances': update_data['distances'],
                'nouvelle_position': update_data['nouvelle_position'],
                'debug_info': {
                    'timestamp_recu': timestamp_str,
                    'timestamp_local_final': new_datetime.isoformat(),
                    'date_finale': new_date.isoformat(),
                    'heure_finale': new_heure.strftime('%H:%M:%S')
                }
            })
            
        except TagRfid.DoesNotExist:
            return Response({
                'error': f'Tag RFID {tag_num_serie} non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"ERREUR GÉNÉRALE: {str(e)}")
            import traceback
            print(f"Traceback complet: {traceback.format_exc()}")
            return Response({
                'error': f'Erreur: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_current_coordinates(self, messeur):
        """
        Obtenir les coordonnées GPS actuelles du MesseurTracking
        """
        # Essayer d'obtenir les coordonnées depuis les champs directs
        if hasattr(messeur, 'latitude') and hasattr(messeur, 'longitude'):
            if messeur.latitude and messeur.longitude:
                return float(messeur.latitude), float(messeur.longitude)
        
        # Sinon, essayer d'obtenir depuis la dernière position dans l'historique
        derniere_position = PositionHistorique.objects.filter(
            messeur_tracking=messeur
        ).order_by('-timestamp').first()
        
        if derniere_position and derniere_position.latitude and derniere_position.longitude:
            return float(derniere_position.latitude), float(derniere_position.longitude)
        
        # Par défaut, retourner None si pas de coordonnées
        return None, None
    
    def get_location_from_coordinates(self, latitude, longitude):
        """
        Obtenir le nom du lieu à partir des coordonnées GPS - VERSION AMÉLIORÉE
        Évite les coordonnées GPS brutes en utilisant plusieurs méthodes
        """
        if not latitude or not longitude:
            return 'Position GPS inconnue'
        
        try:
            print(f"Tentative géolocalisation pour: {latitude}, {longitude}")
            
            geolocation_service = GeolocationService()
            
            # MÉTHODE 1: Utiliser process_location_by_coordinates
            try:
                result = geolocation_service.process_location_by_coordinates(
                    float(latitude), float(longitude)
                )
                
                if result and 'lieu' in result and result['lieu']:
                    lieu_trouve = result['lieu']
                    # Vérifier que ce n'est pas juste des coordonnées
                    if not lieu_trouve.startswith('GPS(') and len(lieu_trouve) > 10:
                        print(f"Lieu trouvé (méthode 1): {lieu_trouve}")
                        return lieu_trouve
                
            except Exception as e1:
                print(f"Erreur méthode 1: {str(e1)}")
            
            # MÉTHODE 2: Utiliser reverse_geocode directement
            try:
                reverse_result = geolocation_service.geocoder.reverse_geocode(
                    float(latitude), float(longitude)
                )
                
                if reverse_result:
                    print(f"Résultat géocodage inverse: {reverse_result}")
                    
                    # Extraire le lieu à partir de formatted_address
                    if 'formatted_address' in reverse_result and reverse_result['formatted_address']:
                        formatted_address = reverse_result['formatted_address']
                        # Prendre les deux premiers éléments de l'adresse
                        address_parts = formatted_address.split(',')
                        if len(address_parts) >= 2:
                            lieu_extrait = f"{address_parts[0].strip()}, {address_parts[1].strip()}"
                            print(f"Lieu extrait (méthode 2): {lieu_extrait}")
                            return lieu_extrait
                        elif len(address_parts) == 1 and len(address_parts[0].strip()) > 5:
                            lieu_extrait = address_parts[0].strip()
                            print(f"Lieu extrait simple (méthode 2): {lieu_extrait}")
                            return lieu_extrait
                    
                    # Fallback vers address_components
                    if 'address_components' in reverse_result:
                        address = reverse_result['address_components']
                        lieu_parts = []
                        
                        # Prioriser ville > commune > village > quartier
                        for key in ['city', 'town', 'village', 'suburb', 'municipality']:
                            if key in address and address[key]:
                                lieu_parts.append(address[key])
                                break
                        
                        if 'state' in address and address['state'] and len(lieu_parts) > 0:
                            lieu_parts.append(address['state'])
                        
                        if lieu_parts:
                            lieu_extrait = ', '.join(lieu_parts)
                            print(f"Lieu extrait (components): {lieu_extrait}")
                            return lieu_extrait
                            
            except Exception as e2:
                print(f"Erreur méthode 2: {str(e2)}")
            
            # MÉTHODE 3: Base de données de lieux connus
            try:
                lieu_connu = self._get_lieu_from_coordinates_database(latitude, longitude)
                if lieu_connu:
                    print(f"Lieu trouvé dans la base de données: {lieu_connu}")
                    return lieu_connu
            except Exception as e3:
                print(f"Erreur avec base de données de lieux: {str(e3)}")
            
            # MÉTHODE 4: Fallback intelligent basé sur les coordonnées géographiques
            return self._get_lieu_approximatif(latitude, longitude)
            
        except Exception as e:
            print(f"Erreur géolocalisation complète: {str(e)}")
            return self._get_lieu_approximatif(latitude, longitude)

    def _get_lieu_from_coordinates_database(self, latitude, longitude):
        """
        Base de données de lieux connus en Algérie pour améliorer la géolocalisation
        """
        lat_float = float(latitude)
        lng_float = float(longitude)
        
        # Définir des zones géographiques connues avec une marge d'erreur
        zones_connues = [
            # Format: (lat_min, lat_max, lng_min, lng_max, nom_lieu)
            (34.87, 34.89, -1.32, -1.31, "Tlemcen, Algérie"),
            (36.77, 36.78, 3.05, 3.06, "Alger, Algérie"),
            (35.69, 35.71, -0.66, -0.64, "Oran, Algérie"),
            (36.35, 36.37, 6.60, 6.62, "Béjaïa, Algérie"),
            (36.91, 36.93, 7.75, 7.77, "Annaba, Algérie"),
            (35.37, 35.39, 1.31, 1.33, "Boumerdès, Algérie"),
            (36.64, 36.66, 3.13, 3.15, "Tizi Ouzou, Algérie"),
            (35.20, 35.22, -1.15, -1.13, "Sidi Bel Abbès, Algérie"),
            (36.46, 36.48, 2.23, 2.25, "Blida, Algérie"),
            (34.83, 34.85, 5.73, 5.75, "Ouargla, Algérie"),
            (22.77, 22.79, 5.51, 5.53, "Tamanrasset, Algérie"),
            (31.63, 31.65, 2.10, 2.12, "Ghardaïa, Algérie")
        ]
        
        # Vérifier si les coordonnées correspondent à une zone connue
        for lat_min, lat_max, lng_min, lng_max, nom_lieu in zones_connues:
            if lat_min <= lat_float <= lat_max and lng_min <= lng_float <= lng_max:
                return nom_lieu
        
        return None

    def _get_lieu_approximatif(self, latitude, longitude):
        """
        Fallback intelligent pour déterminer le lieu approximatif
        """
        try:
            lat_float = float(latitude)
            lng_float = float(longitude)
            
            # Algérie
            if 18.0 <= lat_float <= 37.0 and -8.0 <= lng_float <= 12.0:
                # Subdivisions par région
                if 34.8 <= lat_float <= 35.0 and -1.5 <= lng_float <= -1.0:
                    return "Tlemcen, Algérie"
                elif 36.7 <= lat_float <= 36.8 and 3.0 <= lng_float <= 3.1:
                    return "Alger, Algérie"
                elif 35.7 <= lat_float <= 35.8 and -0.7 <= lng_float <= -0.6:
                    return "Oran, Algérie"
                elif 36.3 <= lat_float <= 36.4 and 6.6 <= lng_float <= 6.7:
                    return "Béjaïa, Algérie"
                elif 34.0 <= lat_float <= 37.0 and -2.0 <= lng_float <= 8.0:
                    return "Nord de l'Algérie"
                elif 28.0 <= lat_float <= 34.0:
                    return "Centre de l'Algérie"
                else:
                    return "Sud de l'Algérie"
            
            # Maroc
            elif 27.0 <= lat_float <= 36.0 and -13.0 <= lng_float <= -1.0:
                return "Maroc"
            
            # Tunisie
            elif 30.0 <= lat_float <= 37.5 and 7.0 <= lng_float <= 12.0:
                return "Tunisie"
            
            # Autres régions
            elif 30.0 <= lat_float <= 48.0 and -10.0 <= lng_float <= 30.0:
                return "Afrique du Nord"
            else:
                return f"Position ({lat_float:.3f}, {lng_float:.3f})"
                
        except Exception:
            return f"GPS({latitude}, {longitude})"
    
    def broadcast_sse_update(self, data):
        """
        Fonction pour broadcaster les mises à jour SSE
        """
        # Stocker la mise à jour dans le cache pour les clients SSE
        cache_key = f"sse_update_{data['trajet_id']}"
        cache.set(cache_key, json.dumps(data), 300)  # 5 minutes
        
        # Stocker aussi pour tous les trajets
        cache.set("sse_update_all", json.dumps(data), 300)
        
        print(f"Mise à jour SSE broadcastée pour trajet {data['trajet_id']}")
class UpdatePositionRealTimeView(APIView):
    def post(self, request):
        print(f"CLASSE UTILISÉE: {self.__class__.__name__}")
        
        tag_num_serie = request.data.get('tag_rfid_num_serie')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        timestamp = request.data.get('timestamp')
        
        print(f"DEBUG - Données reçues:")
        print(f"   Tag: {tag_num_serie}")
        print(f"   Coordonnées: {latitude}, {longitude}")
        print(f"   Timestamp brut: {timestamp}")
        
        if not all([tag_num_serie, latitude, longitude, timestamp]):
            return Response({
                'error': 'tag_rfid_num_serie, latitude, longitude ET timestamp sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Géolocalisation inverse automatique pour déterminer le lieu
        lieu = self.get_location_from_coordinates(latitude, longitude)
        
        try:
            # Trouver le tag RFID
            tag_rfid = TagRfid.objects.get(num_serie=tag_num_serie)
            
            # ====================================================================
            # MODIFICATION: Logique de sélection avec passage au trajet suivant
            # ====================================================================
            # Trouver TOUS les MesseurTracking avec ce tag RFID
            messeurs_candidats = MesseurTracking.objects.filter(
                capture_rfid=tag_rfid
            ).select_related('path', 'object_tracking').order_by('path__id')  # Trier par ID croissant
            
            if not messeurs_candidats.exists():
                return Response({
                    'error': f'Aucun trajet actif pour le tag {tag_num_serie}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            #  NOUVELLE LOGIQUE: Sélection avec passage automatique au trajet suivant
            messeur = None
            raison_selection = ""
            
            print(f" Trajets trouvés pour le tag {tag_num_serie}:")
            for m in messeurs_candidats:
                print(f"   - PathTemplate ID: {m.path.id}, État objet: {m.object_tracking.etat}, Position: {m.lieu}")
            
            if messeurs_candidats.count() > 1:
                # Chercher le trajet actuel (le plus petit ID qui n'est pas terminé)
                trajet_actuel = None
                trajet_suivant = None
                
                for candidat in messeurs_candidats:
                    trajet_termine = self._is_trajet_termine(candidat)
                    
                    if not trajet_termine and trajet_actuel is None:
                        # Premier trajet non terminé = trajet actuel
                        trajet_actuel = candidat
                    elif trajet_termine and trajet_suivant is None:
                        # Si le trajet actuel est terminé, chercher le suivant
                        trajet_suivant_candidat = messeurs_candidats.filter(
                            path__id__gt=candidat.path.id
                        ).first()
                        if trajet_suivant_candidat:
                            trajet_suivant = trajet_suivant_candidat
                            break
                
                # DÉCISION DE SÉLECTION
                if trajet_actuel and not self._is_trajet_termine(trajet_actuel):
                    # Cas normal : utiliser le trajet actuel non terminé
                    messeur = trajet_actuel
                    raison_selection = f"PathTemplate ID {messeur.path.id} (trajet actuel en cours)"
                    print(f"Trajet actuel sélectionné: {raison_selection}")
                    
                elif trajet_suivant:
                    # CAS SPÉCIAL : Le trajet actuel est terminé → Passer au suivant
                    messeur = trajet_suivant
                    raison_selection = f"PathTemplate ID {messeur.path.id} (passage automatique au trajet suivant)"
                    print(f" Passage au trajet suivant: {raison_selection}")
                    
                    # Mettre à jour l'état de l'objet pour le nouveau trajet
                    if messeur.object_tracking.etat == 'reçu':
                        messeur.object_tracking.etat = 'stocke'  # L'objet repart depuis le nouveau point de départ
                        messeur.object_tracking.save()
                        print(f" État objet changé: reçu → stocke (nouveau trajet)")
                        
                else:
                    # Fallback : prendre le premier trajet disponible
                    messeur = messeurs_candidats.first()
                    raison_selection = f"PathTemplate ID {messeur.path.id} (fallback - premier disponible)"
                    print(f"  Fallback: {raison_selection}")
                    
            else:
                # Un seul trajet disponible
                messeur = messeurs_candidats.first()
                
                #  VÉRIFIER SI CE TRAJET UNIQUE EST TERMINÉ
                if self._is_trajet_termine(messeur):
                    # Chercher s'il y a un trajet suivant logique
                    trajet_suivant = MesseurTracking.objects.filter(
                        capture_rfid=tag_rfid,
                        path__id__gt=messeur.path.id
                    ).select_related('path', 'object_tracking').first()
                    
                    if trajet_suivant:
                        messeur = trajet_suivant
                        raison_selection = f"PathTemplate ID {messeur.path.id} (trajet unique terminé → suivant)"
                        print(f" Trajet unique terminé, passage au suivant: {raison_selection}")
                        
                        # Réinitialiser l'état de l'objet
                        if messeur.object_tracking.etat == 'reçu':
                            messeur.object_tracking.etat = 'stocke'
                            messeur.object_tracking.save()
                    else:
                        raison_selection = f"PathTemplate ID {messeur.path.id} (unique, terminé, aucun suivant)"
                        print(f"  Trajet unique terminé sans suite: {raison_selection}")
                else:
                    raison_selection = f"PathTemplate ID {messeur.path.id} (unique, en cours)"
                    print(f" Trajet unique en cours: {raison_selection}")
            
            # Sauvegarder l'ancienne position actuelle AVANT de la modifier
            previous_lieu = messeur.lieu
            previous_latitude, previous_longitude = self.get_current_coordinates(messeur)
            
            # ====================================================================
            # TRAITEMENT TIMESTAMP - VERSION ULTRA SIMPLE
            # ====================================================================
            try:
                # Nettoyer le timestamp
                timestamp_clean = timestamp.strip()
                timestamp_clean = timestamp_clean.replace('Z', '')
                timestamp_clean = timestamp_clean.replace('+00:00', '')
                timestamp_clean = timestamp_clean.replace('T', ' ')
                
                print(f"Timestamp nettoyé: '{timestamp_clean}'")
                
                # Format attendu: "YYYY-MM-DD HH:MM:SS"
                if ' ' not in timestamp_clean:
                    return Response({
                        'error': 'Format timestamp invalide. Format requis: YYYY-MM-DD HH:MM:SS',
                        'timestamp_recu': timestamp
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                date_str, time_str = timestamp_clean.split(' ', 1)
                
                # ================================================================
                # PARSER LA DATE - SIMPLE
                # ================================================================
                try:
                    year, month, day = map(int, date_str.split('-'))
                    new_date = date(year, month, day)
                    print(f"Date créée: {new_date}")
                except ValueError as e:
                    return Response({
                        'error': f'Date invalide: {date_str} - {str(e)}',
                        'format_requis': 'YYYY-MM-DD'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # ================================================================
                # PARSER L'HEURE - SIMPLE SANS CONVERSION
                # ================================================================
                try:
                    time_parts = time_str.split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                    second = int(float(time_parts[2])) if len(time_parts) > 2 else 0
                    
                    print(f"Composants heure: {hour}h {minute}m {second}s")
                    
                    # VALIDATION STRICTE
                    if not (0 <= hour <= 23):
                        raise ValueError(f"Heure invalide: {hour} (doit être entre 0 et 23)")
                    if not (0 <= minute <= 59):
                        raise ValueError(f"Minutes invalides: {minute}")
                    if not (0 <= second <= 59):
                        raise ValueError(f"Secondes invalides: {second}")
                    
                    # ============================================================
                    # CRÉER L'HEURE SOUS FORME DE STRING POUR ÉVITER CONVERSIONS
                    # ============================================================
                    new_heure_str = f"{hour:02d}:{minute:02d}:{second:02d}"
                    print(f"Heure en string: {new_heure_str}")
                    
                except ValueError as e:
                    return Response({
                        'error': f'Heure invalide: {time_str} - {str(e)}',
                        'format_requis': 'HH:MM:SS'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # ================================================================
                # CRÉER DATETIME POUR HISTORIQUE SEULEMENT
                # ================================================================
                new_datetime_simple = datetime.combine(new_date, datetime_time(hour, minute, second))
                
                # Le rendre timezone-aware avec UTC par défaut
                from django.utils import timezone as django_timezone
                new_datetime = django_timezone.make_aware(new_datetime_simple, timezone=django_timezone.utc)
                
                print(f" DateTime final: {new_datetime}")
                
            except Exception as e:
                print(f" Erreur parsing: {str(e)}")
                return Response({
                    'error': f'Erreur parsing timestamp: {str(e)}',
                    'timestamp_recu': timestamp,
                    'format_requis': 'YYYY-MM-DD HH:MM:SS'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ====================================================================
            # LOGIQUE HISTORIQUE ET ÉTAT DE L'OBJET
            # ====================================================================
            
            # ÉTAPE 1: SAUVEGARDER L'ANCIENNE POSITION
            if messeur.lieu and messeur.date_prevu and messeur.heure:
                try:
                    if isinstance(messeur.heure, str):
                        hour_parts = messeur.heure.split(':')
                        old_hour = int(hour_parts[0])
                        old_minute = int(hour_parts[1])
                        old_second = int(hour_parts[2]) if len(hour_parts) > 2 else 0
                        old_time = datetime_time(old_hour, old_minute, old_second)
                    else:
                        old_time = messeur.heure
                    
                    ancienne_datetime_simple = datetime.combine(messeur.date_prevu, old_time)
                    ancienne_datetime = django_timezone.make_aware(ancienne_datetime_simple, timezone=django_timezone.utc)
                except Exception as e:
                    print(f"Erreur ancienne datetime: {e}")
                    ancienne_datetime = new_datetime
                
                ancienne_position = PositionHistorique.objects.create(
                    messeur_tracking=messeur,
                    lieu=messeur.lieu,
                    latitude=previous_latitude if previous_latitude else 0.0,
                    longitude=previous_longitude if previous_longitude else 0.0,
                    timestamp=ancienne_datetime,
                    date_sortie=new_datetime
                )
                
                if previous_lieu != lieu:
                    premiere_entree_ancien_lieu = PositionHistorique.objects.filter(
                        messeur_tracking=messeur,
                        lieu=previous_lieu,
                        date_entree__isnull=False
                    ).order_by('timestamp').first()
                    
                    if premiere_entree_ancien_lieu and premiere_entree_ancien_lieu.date_entree:
                        duree_dans_ancien_lieu = new_datetime - premiere_entree_ancien_lieu.date_entree
                        ancienne_position.duree_dans_lieu = duree_dans_ancien_lieu
                        ancienne_position.date_entree = premiere_entree_ancien_lieu.date_entree
                        ancienne_position.save()
            
            # ÉTAPE 2: CRÉER L'ENTRÉE POUR LA NOUVELLE POSITION
            nouvelle_position = PositionHistorique.objects.create(
                messeur_tracking=messeur,
                lieu=lieu,
                latitude=float(latitude),
                longitude=float(longitude),
                timestamp=new_datetime,
                date_entree=new_datetime
            )
            
            # ====================================================================
            # ÉTAPE 3: CALCULER LA DURÉE DE PASSAGE - CORRECTION POUR DURÉE RÉELLE
            # ====================================================================
            if previous_lieu == lieu:
                # L'objet est toujours dans le même lieu
                premiere_entree = PositionHistorique.objects.filter(
                    messeur_tracking=messeur,
                    lieu=lieu,
                    date_entree__isnull=False
                ).order_by('timestamp').first()
                
                if premiere_entree and premiere_entree.date_entree:
                    #  CALCUL DE LA VRAIE DURÉE : nouveau temps - première entrée
                    duree_dans_lieu = new_datetime - premiere_entree.date_entree
                    
                    # Obtenir le nombre total de secondes
                    total_seconds = int(duree_dans_lieu.total_seconds())
                    
                    #  PAS DE LIMITATION - CALCULER LA VRAIE DURÉE
                    if total_seconds < 0:
                        # Si la durée est négative, réinitialiser
                        messeur.duree_passage = "00:00:00"
                        print(" Durée négative détectée, réinitialisée à 00:00:00")
                    else:
                        # Calculer heures, minutes, secondes SANS limitation
                        heures = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        secondes = total_seconds % 60
                        
                        #  AUTORISER LES DURÉES > 24H (ex: 25:30:45, 100:15:30, etc.)
                        messeur.duree_passage = f"{heures:02d}:{minutes:02d}:{secondes:02d}"
                        print(f" Durée réelle calculée: {messeur.duree_passage} ({total_seconds} secondes total)")
                else:
                    messeur.duree_passage = "00:00:00"
            else:
                # L'objet a changé de lieu - commencer un nouveau compteur
                messeur.duree_passage = "00:00:00"
                print(" Changement de lieu détecté - durée réinitialisée")
            
            # LOGIQUE ÉTAT DE L'OBJET
            objet = messeur.object_tracking
            path = messeur.path
            
            def calculate_distance(lat1, lon1, lat2, lon2):
                R = 6371
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                return R * c * 1000
            
            distance_source = calculate_distance(
                float(latitude), float(longitude),
                path.latitude_src, path.longitude_src
            )
            
            distance_destination = calculate_distance(
                float(latitude), float(longitude),
                path.latitude_dest, path.longitude_dest
            )
            
            if distance_source <= 100:
                if objet.etat != 'stocke':
                    objet.etat = 'stocke'
                    objet.save()
            elif distance_destination <= 100:
                if objet.etat != 'reçu':
                    objet.etat = 'reçu'
                    objet.save()
            else:
                if objet.etat != 'en_transit':
                    objet.etat = 'en_transit'
                    objet.save()
            
            # ====================================================================
            # SAUVEGARDE AVEC GESTION INTELLIGENTE DES DURÉES > 24H
            # ====================================================================
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    duree_str = str(messeur.duree_passage) if messeur.duree_passage else "00:00:00"
                    
                    # ✅ VALIDATION ET GESTION DES DURÉES > 24H
                    duree_parts = duree_str.split(':')
                    if len(duree_parts) == 3:
                        heures_int = int(duree_parts[0])
                        
                        if heures_int >= 24:
                            # PostgreSQL TIME ne supporte pas > 23:59:59
                            print(f"⚠️  Durée > 24h détectée: {duree_str}")
                            
                            # Convertir en format descriptif pour les notes
                            jours = heures_int // 24
                            heures_restantes = heures_int % 24
                            
                            duree_descriptive = f"{jours}j {heures_restantes:02d}:{duree_parts[1]}:{duree_parts[2]}"
                            print(f" Format descriptif: {duree_descriptive}")
                            
                            # Pour la base de données, utiliser la durée modulo 24h + note
                            duree_pour_db = f"{heures_restantes:02d}:{duree_parts[1]}:{duree_parts[2]}"
                            
                            #  VÉRIFIER SI LA COLONNE 'notes' EXISTE
                            cursor.execute("""
                                SELECT column_name FROM information_schema.columns 
                                WHERE table_name = 'captures_messeurtracking' AND column_name = 'notes'
                            """)
                            notes_column_exists = cursor.fetchone() is not None
                            
                            if notes_column_exists:
                                # Avec notes
                                cursor.execute("""
                                    UPDATE captures_messeurtracking 
                                    SET lieu = %s, date_prevu = %s, heure = %s, 
                                        duree_passage = %s,
                                        notes = CONCAT(COALESCE(notes, ''), ' [Durée totale: ', %s, ']')
                                    WHERE id = %s
                                """, [
                                    lieu, 
                                    new_date.strftime('%Y-%m-%d'), 
                                    new_heure_str,
                                    duree_pour_db,  # TIME valide
                                    duree_descriptive,  # Durée complète en note
                                    messeur.id
                                ])
                            else:
                                # Sans notes - juste la durée limitée
                                cursor.execute("""
                                    UPDATE captures_messeurtracking 
                                    SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                                    WHERE id = %s
                                """, [
                                    lieu, 
                                    new_date.strftime('%Y-%m-%d'), 
                                    new_heure_str,
                                    duree_pour_db,
                                    messeur.id
                                ])
                                
                            # Stocker la vraie durée pour la réponse
                            duree_response = duree_descriptive
                        else:
                            # Durée normale < 24h
                            cursor.execute("""
                                UPDATE captures_messeurtracking 
                                SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                                WHERE id = %s
                            """, [
                                lieu, 
                                new_date.strftime('%Y-%m-%d'), 
                                new_heure_str,
                                duree_str,
                                messeur.id
                            ])
                            duree_response = duree_str
                    else:
                        # Format invalide
                        duree_str = "00:00:00"
                        duree_response = duree_str
                        cursor.execute("""
                            UPDATE captures_messeurtracking 
                            SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                            WHERE id = %s
                        """, [
                            lieu, 
                            new_date.strftime('%Y-%m-%d'), 
                            new_heure_str,
                            duree_str,
                            messeur.id
                        ])

                print(f"Sauvegarde avec durée réelle: {duree_response if 'duree_response' in locals() else duree_str}")
                
                # Recharger l'objet
                messeur.refresh_from_db()
                
            except Exception as sql_error:
                print(f"Erreur raw SQL: {sql_error}")
                return Response({
                    'error': f'Erreur sauvegarde SQL: {str(sql_error)}',
                    'debug': {
                        'duree_calculee': duree_str if 'duree_str' in locals() else "N/A",
                        'total_seconds': total_seconds if 'total_seconds' in locals() else 0
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # ENVOYER MISE À JOUR SSE
            update_data = {
                'type': 'position_update',
                'trajet_id': messeur.path.id,
                'tag_rfid': tag_num_serie,
                'objet_nom': f"{messeur.object_tracking.categorie}_{tag_num_serie}",
                'etat_objet': objet.etat,
                'etat_change': previous_lieu != lieu,
                'distances': {
                    'source': round(distance_source, 2),
                    'destination': round(distance_destination, 2)
                },
                'nouvelle_position': {
                    'lieu': lieu,
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': new_date.isoformat(),
                    'heure': new_heure_str,
                    'duree_passage': duree_response if 'duree_response' in locals() else str(messeur.duree_passage)
                }
            }
            
            self.broadcast_sse_update(update_data)
            
            # ====================================================================
            # RÉPONSE AVEC INFORMATIONS SUR LA SÉLECTION DU TRAJET
            # ====================================================================
            response_data = {
                'success': True,
                'message': f'Position mise à jour pour {tag_num_serie}',
                'trajet_id': messeur.path.id,
                'etat_objet': objet.etat,
                'duree_passage': duree_response if 'duree_response' in locals() else str(messeur.duree_passage),
                'distances': update_data['distances'],
                'nouvelle_position': update_data['nouvelle_position'],
                'debug_info': {
                    'timestamp_recu': timestamp,
                    'date_finale': new_date.isoformat(),
                    'heure_finale_string': new_heure_str,
                    'duree_finale_reelle': duree_response if 'duree_response' in locals() else str(messeur.duree_passage),
                    'methode': 'Calcul durée réelle sans limitation'
                }
            }
            
            # Ajouter des informations sur la sélection si plusieurs trajets étaient disponibles
            if messeurs_candidats.count() > 1:
                response_data['selection_info'] = {
                    'trajets_disponibles': messeurs_candidats.count(),
                    'trajet_selectionne': {
                        'path_template_id': messeur.path.id,
                        'nom_trajet': messeur.path.nom,
                        'raison_selection': raison_selection
                    },
                    'autres_trajets': [
                        {
                            'path_template_id': m.path.id,
                            'nom_trajet': m.path.nom,
                            'date_debut': m.date_debut.isoformat(),
                            'etat_objet': m.object_tracking.etat,
                            'est_termine': self._is_trajet_termine(m)
                        }
                        for m in messeurs_candidats.exclude(id=messeur.id)
                    ]
                }
            
            return Response(response_data)
            
        except TagRfid.DoesNotExist:
            return Response({
                'error': f'Tag RFID {tag_num_serie} non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"ERREUR GÉNÉRALE: {str(e)}")
            return Response({
                'error': f'Erreur: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _is_trajet_termine(self, messeur):
        """
        Vérifie si un trajet est terminé (objet arrivé à destination)
        
        Args:
            messeur: Instance MesseurTracking
            
        Returns:
            bool: True si le trajet est terminé, False sinon
        """
        try:
            objet = messeur.object_tracking
            path = messeur.path
            
            # ✅ CRITÈRE 1: État de l'objet = "reçu"
            if objet.etat == 'reçu':
                print(f"   Trajet {path.id} terminé: objet état 'reçu'")
                return True
            
            # ✅ CRITÈRE 2: Position actuelle = destination
            if messeur.lieu and path.destination:
                lieu_actuel_lower = messeur.lieu.lower()
                destination_lower = path.destination.lower()
                
                # Correspondance exacte
                if lieu_actuel_lower == destination_lower:
                    print(f"   Trajet {path.id} terminé: position = destination exacte")
                    return True
                
                # Correspondance partielle
                destination_mots = destination_lower.split()
                for mot in destination_mots:
                    if len(mot) > 3 and mot in lieu_actuel_lower:
                        print(f"   Trajet {path.id} terminé: position contient '{mot}' de destination")
                        return True
                
                # Correspondance inverse
                lieu_mots = lieu_actuel_lower.split()
                for mot in lieu_mots:
                    if len(mot) > 3 and mot in destination_lower:
                        print(f"   Trajet {path.id} terminé: destination contient '{mot}' de position")
                        return True
            
            #  CRITÈRE 3: Historique de passage à destination
            if path.destination:
                destination_dans_historique = PositionHistorique.objects.filter(
                    messeur_tracking=messeur,
                    lieu__icontains=path.destination.split(',')[0] if ',' in path.destination else path.destination.split()[0]
                ).exists()
                
                if destination_dans_historique:
                    print(f"   Trajet {path.id} terminé: destination dans historique")
                    return True
            
            #  CRITÈRE 4: Calcul de distance géographique (< 100m de destination)
            try:
                if hasattr(messeur, 'latitude') and hasattr(messeur, 'longitude'):
                    if messeur.latitude and messeur.longitude and path.latitude_dest and path.longitude_dest:
                        def calculate_distance(lat1, lon1, lat2, lon2):
                            import math
                            R = 6371000  # Rayon terre en mètres
                            dlat = math.radians(lat2 - lat1)
                            dlon = math.radians(lon2 - lon1)
                            a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
                            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                            return R * c
                        
                        distance_destination = calculate_distance(
                            float(messeur.latitude), float(messeur.longitude),
                            float(path.latitude_dest), float(path.longitude_dest)
                        )
                        
                        if distance_destination <= 100:  # 100 mètres
                            print(f"   Trajet {path.id} terminé: distance destination = {distance_destination:.1f}m")
                            return True
                        
                # Sinon, vérifier depuis PositionHistorique
                else:
                    derniere_position = PositionHistorique.objects.filter(
                        messeur_tracking=messeur
                    ).order_by('-timestamp').first()
                    
                    if (derniere_position and derniere_position.latitude and derniere_position.longitude 
                        and path.latitude_dest and path.longitude_dest):
                        
                        distance_destination = calculate_distance(
                            float(derniere_position.latitude), float(derniere_position.longitude),
                            float(path.latitude_dest), float(path.longitude_dest)
                        )
                        
                        if distance_destination <= 100:
                            print(f"   Trajet {path.id} terminé: distance destination (historique) = {distance_destination:.1f}m")
                            return True
                            
            except Exception as e:
                print(f"   Erreur calcul distance pour trajet {path.id}: {e}")
            
            print(f"   Trajet {path.id} actif: aucun critère de fin détecté")
            return False
            
        except Exception as e:
            print(f"   Erreur vérification trajet {messeur.path.id}: {e}")
            return False

    # Les autres méthodes restent inchangées...
    def get_current_coordinates(self, messeur):
        """
        Obtenir les coordonnées GPS actuelles du MesseurTracking
        """
        # Essayer d'obtenir les coordonnées depuis les champs directs
        if hasattr(messeur, 'latitude') and hasattr(messeur, 'longitude'):
            if messeur.latitude and messeur.longitude:
                return float(messeur.latitude), float(messeur.longitude)
        
        # Sinon, essayer d'obtenir depuis la dernière position dans l'historique
        derniere_position = PositionHistorique.objects.filter(
            messeur_tracking=messeur
        ).order_by('-timestamp').first()
        
        if derniere_position and derniere_position.latitude and derniere_position.longitude:
            return float(derniere_position.latitude), float(derniere_position.longitude)
        
        # Par défaut, retourner None si pas de coordonnées
        return None, None
    
    def get_location_from_coordinates(self, latitude, longitude):
        """
        Obtenir le nom du lieu à partir des coordonnées GPS en utilisant la géolocalisation inverse
        """
        if not latitude or not longitude:
            return 'Position GPS inconnue'
        
        try:
            geolocation_service = GeolocationService()
            result = geolocation_service.geocoder.reverse_geocode(
                float(latitude), float(longitude)
            )
            
            # Extraire le nom du lieu principal à partir des composants d'adresse
            if result and 'address_components' in result:
                address = result['address_components']
                
                # Prioriser ville > commune > village > quartier
                lieu_parts = []
                
                if 'city' in address:
                    lieu_parts.append(address['city'])
                elif 'town' in address:
                    lieu_parts.append(address['town'])
                elif 'village' in address:
                    lieu_parts.append(address['village'])
                elif 'suburb' in address:
                    lieu_parts.append(address['suburb'])
                elif 'municipality' in address:
                    lieu_parts.append(address['municipality'])
                
                if 'state' in address and len(lieu_parts) > 0:
                    lieu_parts.append(address['state'])
                
                if lieu_parts:
                    lieu = ', '.join(lieu_parts)
                else:
                    # Utiliser le nom formaté et prendre les premiers éléments
                    formatted_address = result.get('formatted_address', '')
                    address_parts = formatted_address.split(',')
                    if len(address_parts) >= 2:
                        lieu = f"{address_parts[0].strip()}, {address_parts[1].strip()}"
                    else:
                        lieu = address_parts[0].strip() if address_parts else f"GPS({latitude}, {longitude})"
                        
                return lieu if lieu else f"GPS({latitude}, {longitude})"
            else:
                return f"GPS({latitude}, {longitude})"
                
        except Exception as e:
            # En cas d'erreur, utiliser les coordonnées
            print(f"Erreur géolocalisation: {str(e)}")
            return f"GPS({latitude}, {longitude})"
    
    def broadcast_sse_update(self, data):
        """
        Fonction pour broadcaster les mises à jour SSE
        """
        # Stocker la mise à jour dans le cache pour les clients SSE
        cache_key = f"sse_update_{data['trajet_id']}"
        cache.set(cache_key, json.dumps(data), 300)  # 5 minutes
        
        # Stocker aussi pour tous les trajets
        cache.set("sse_update_all", json.dumps(data), 300)
class UpdatePositionRealTimeView7(APIView):
    def post(self, request):
        print(f"🎯 CLASSE UTILISÉE: {self.__class__.__name__}")
        
        tag_num_serie = request.data.get('tag_rfid_num_serie')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        timestamp = request.data.get('timestamp')
        
        print(f"DEBUG - Données reçues:")
        print(f"   Tag: {tag_num_serie}")
        print(f"   Coordonnées: {latitude}, {longitude}")
        print(f"   Timestamp brut: {timestamp}")
        
        if not all([tag_num_serie, latitude, longitude, timestamp]):
            return Response({
                'error': 'tag_rfid_num_serie, latitude, longitude ET timestamp sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Géolocalisation inverse automatique pour déterminer le lieu
        lieu = self.get_location_from_coordinates(latitude, longitude)
        
        try:
            # Trouver le tag RFID
            tag_rfid = TagRfid.objects.get(num_serie=tag_num_serie)
            
            # ====================================================================
            # MODIFICATION: Choisir le trajet avec l'ID le plus petit
            # ====================================================================
            # Trouver TOUS les MesseurTracking avec ce tag RFID
            messeurs_candidats = MesseurTracking.objects.filter(
                capture_rfid=tag_rfid
            ).select_related('path').order_by('-date_debut')
            
            if not messeurs_candidats.exists():
                return Response({
                    'error': f'Aucun trajet actif pour le tag {tag_num_serie}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Si plusieurs trajets trouvés, choisir celui avec l'ID PathTemplate le plus petit
            if messeurs_candidats.count() > 1:
                print(f"🔍 Plusieurs trajets trouvés pour le tag {tag_num_serie}:")
                for m in messeurs_candidats:
                    print(f"   - MesseurTracking ID: {m.id}, PathTemplate ID: {m.path.id}, Date: {m.date_debut}")
                
                # Trier par ID de PathTemplate croissant et prendre le premier
                messeur = messeurs_candidats.order_by('path__id').first()
                print(f"✅ Trajet sélectionné: PathTemplate ID {messeur.path.id} (le plus petit)")
            else:
                messeur = messeurs_candidats.first()
                print(f"✅ Un seul trajet trouvé: PathTemplate ID {messeur.path.id}")
            
            # Sauvegarder l'ancienne position actuelle AVANT de la modifier
            previous_lieu = messeur.lieu
            previous_latitude, previous_longitude = self.get_current_coordinates(messeur)
            
            # ====================================================================
            # TRAITEMENT TIMESTAMP - VERSION ULTRA SIMPLE
            # ====================================================================
            try:
                # Nettoyer le timestamp
                timestamp_clean = timestamp.strip()
                timestamp_clean = timestamp_clean.replace('Z', '')
                timestamp_clean = timestamp_clean.replace('+00:00', '')
                timestamp_clean = timestamp_clean.replace('T', ' ')
                
                print(f"Timestamp nettoyé: '{timestamp_clean}'")
                
                # Format attendu: "YYYY-MM-DD HH:MM:SS"
                if ' ' not in timestamp_clean:
                    return Response({
                        'error': 'Format timestamp invalide. Format requis: YYYY-MM-DD HH:MM:SS',
                        'timestamp_recu': timestamp
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                date_str, time_str = timestamp_clean.split(' ', 1)
                
                # ================================================================
                # PARSER LA DATE - SIMPLE
                # ================================================================
                try:
                    year, month, day = map(int, date_str.split('-'))
                    new_date = date(year, month, day)
                    print(f"✅ Date créée: {new_date}")
                except ValueError as e:
                    return Response({
                        'error': f'Date invalide: {date_str} - {str(e)}',
                        'format_requis': 'YYYY-MM-DD'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # ================================================================
                # PARSER L'HEURE - SIMPLE SANS CONVERSION
                # ================================================================
                try:
                    time_parts = time_str.split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                    second = int(float(time_parts[2])) if len(time_parts) > 2 else 0
                    
                    print(f"Composants heure: {hour}h {minute}m {second}s")
                    
                    # VALIDATION STRICTE
                    if not (0 <= hour <= 23):
                        raise ValueError(f"Heure invalide: {hour} (doit être entre 0 et 23)")
                    if not (0 <= minute <= 59):
                        raise ValueError(f"Minutes invalides: {minute}")
                    if not (0 <= second <= 59):
                        raise ValueError(f"Secondes invalides: {second}")
                    
                    # ============================================================
                    # CRÉER L'HEURE SOUS FORME DE STRING POUR ÉVITER CONVERSIONS
                    # ============================================================
                    new_heure_str = f"{hour:02d}:{minute:02d}:{second:02d}"
                    print(f"✅ Heure en string: {new_heure_str}")
                    
                except ValueError as e:
                    return Response({
                        'error': f'Heure invalide: {time_str} - {str(e)}',
                        'format_requis': 'HH:MM:SS'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # ================================================================
                # CRÉER DATETIME POUR HISTORIQUE SEULEMENT
                # ================================================================
                new_datetime_simple = datetime.combine(new_date, datetime_time(hour, minute, second))
                
                # Le rendre timezone-aware avec UTC par défaut
                from django.utils import timezone as django_timezone
                new_datetime = django_timezone.make_aware(new_datetime_simple, timezone=django_timezone.utc)
                
                print(f"✅ DateTime final: {new_datetime}")
                
            except Exception as e:
                print(f"❌ Erreur parsing: {str(e)}")
                return Response({
                    'error': f'Erreur parsing timestamp: {str(e)}',
                    'timestamp_recu': timestamp,
                    'format_requis': 'YYYY-MM-DD HH:MM:SS'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ====================================================================
            # LOGIQUE HISTORIQUE ET ÉTAT DE L'OBJET
            # ====================================================================
            
            # ÉTAPE 1: SAUVEGARDER L'ANCIENNE POSITION
            if messeur.lieu and messeur.date_prevu and messeur.heure:
                try:
                    if isinstance(messeur.heure, str):
                        hour_parts = messeur.heure.split(':')
                        old_hour = int(hour_parts[0])
                        old_minute = int(hour_parts[1])
                        old_second = int(hour_parts[2]) if len(hour_parts) > 2 else 0
                        old_time = datetime_time(old_hour, old_minute, old_second)
                    else:
                        old_time = messeur.heure
                    
                    ancienne_datetime_simple = datetime.combine(messeur.date_prevu, old_time)
                    ancienne_datetime = django_timezone.make_aware(ancienne_datetime_simple, timezone=django_timezone.utc)
                except Exception as e:
                    print(f"Erreur ancienne datetime: {e}")
                    ancienne_datetime = new_datetime
                
                ancienne_position = PositionHistorique.objects.create(
                    messeur_tracking=messeur,
                    lieu=messeur.lieu,
                    latitude=previous_latitude if previous_latitude else 0.0,
                    longitude=previous_longitude if previous_longitude else 0.0,
                    timestamp=ancienne_datetime,
                    date_sortie=new_datetime
                )
                
                if previous_lieu != lieu:
                    premiere_entree_ancien_lieu = PositionHistorique.objects.filter(
                        messeur_tracking=messeur,
                        lieu=previous_lieu,
                        date_entree__isnull=False
                    ).order_by('timestamp').first()
                    
                    if premiere_entree_ancien_lieu and premiere_entree_ancien_lieu.date_entree:
                        duree_dans_ancien_lieu = new_datetime - premiere_entree_ancien_lieu.date_entree
                        ancienne_position.duree_dans_lieu = duree_dans_ancien_lieu
                        ancienne_position.date_entree = premiere_entree_ancien_lieu.date_entree
                        ancienne_position.save()
            
            # ÉTAPE 2: CRÉER L'ENTRÉE POUR LA NOUVELLE POSITION
            nouvelle_position = PositionHistorique.objects.create(
                messeur_tracking=messeur,
                lieu=lieu,
                latitude=float(latitude),
                longitude=float(longitude),
                timestamp=new_datetime,
                date_entree=new_datetime
            )
            
            # ====================================================================
            # ÉTAPE 3: CALCULER LA DURÉE DE PASSAGE - CORRECTION POUR DURÉE RÉELLE
            # ====================================================================
            if previous_lieu == lieu:
                # L'objet est toujours dans le même lieu
                premiere_entree = PositionHistorique.objects.filter(
                    messeur_tracking=messeur,
                    lieu=lieu,
                    date_entree__isnull=False
                ).order_by('timestamp').first()
                
                if premiere_entree and premiere_entree.date_entree:
                    # ✅ CALCUL DE LA VRAIE DURÉE : nouveau temps - première entrée
                    duree_dans_lieu = new_datetime - premiere_entree.date_entree
                    
                    # Obtenir le nombre total de secondes
                    total_seconds = int(duree_dans_lieu.total_seconds())
                    
                    # ✅ PAS DE LIMITATION - CALCULER LA VRAIE DURÉE
                    if total_seconds < 0:
                        # Si la durée est négative, réinitialiser
                        messeur.duree_passage = "00:00:00"
                        print("⚠️ Durée négative détectée, réinitialisée à 00:00:00")
                    else:
                        # Calculer heures, minutes, secondes SANS limitation
                        heures = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        secondes = total_seconds % 60
                        
                        # ✅ AUTORISER LES DURÉES > 24H (ex: 25:30:45, 100:15:30, etc.)
                        messeur.duree_passage = f"{heures:02d}:{minutes:02d}:{secondes:02d}"
                        print(f"✅ Durée réelle calculée: {messeur.duree_passage} ({total_seconds} secondes total)")
                else:
                    messeur.duree_passage = "00:00:00"
            else:
                # L'objet a changé de lieu - commencer un nouveau compteur
                messeur.duree_passage = "00:00:00"
                print("🔄 Changement de lieu détecté - durée réinitialisée")
            
            # LOGIQUE ÉTAT DE L'OBJET
            objet = messeur.object_tracking
            path = messeur.path
            
            def calculate_distance(lat1, lon1, lat2, lon2):
                R = 6371
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                return R * c * 1000
            
            distance_source = calculate_distance(
                float(latitude), float(longitude),
                path.latitude_src, path.longitude_src
            )
            
            distance_destination = calculate_distance(
                float(latitude), float(longitude),
                path.latitude_dest, path.longitude_dest
            )
            
            if distance_source <= 100:
                if objet.etat != 'stocke':
                    objet.etat = 'stocke'
                    objet.save()
            elif distance_destination <= 100:
                if objet.etat != 'reçu':
                    objet.etat = 'reçu'
                    objet.save()
            else:
                if objet.etat != 'en_transit':
                    objet.etat = 'en_transit'
                    objet.save()
            
            # ====================================================================
            # SAUVEGARDE AVEC GESTION INTELLIGENTE DES DURÉES > 24H
            # ====================================================================
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    duree_str = str(messeur.duree_passage) if messeur.duree_passage else "00:00:00"
                    
                    # ✅ VALIDATION ET GESTION DES DURÉES > 24H
                    duree_parts = duree_str.split(':')
                    if len(duree_parts) == 3:
                        heures_int = int(duree_parts[0])
                        
                        if heures_int >= 24:
                            # PostgreSQL TIME ne supporte pas > 23:59:59
                            print(f"⚠️  Durée > 24h détectée: {duree_str}")
                            
                            # Convertir en format descriptif pour les notes
                            jours = heures_int // 24
                            heures_restantes = heures_int % 24
                            
                            duree_descriptive = f"{jours}j {heures_restantes:02d}:{duree_parts[1]}:{duree_parts[2]}"
                            print(f"✅ Format descriptif: {duree_descriptive}")
                            
                            # Pour la base de données, utiliser la durée modulo 24h + note
                            duree_pour_db = f"{heures_restantes:02d}:{duree_parts[1]}:{duree_parts[2]}"
                            
                            # ✅ VÉRIFIER SI LA COLONNE 'notes' EXISTE
                            cursor.execute("""
                                SELECT column_name FROM information_schema.columns 
                                WHERE table_name = 'captures_messeurtracking' AND column_name = 'notes'
                            """)
                            notes_column_exists = cursor.fetchone() is not None
                            
                            if notes_column_exists:
                                # Avec notes
                                cursor.execute("""
                                    UPDATE captures_messeurtracking 
                                    SET lieu = %s, date_prevu = %s, heure = %s, 
                                        duree_passage = %s,
                                        notes = CONCAT(COALESCE(notes, ''), ' [Durée totale: ', %s, ']')
                                    WHERE id = %s
                                """, [
                                    lieu, 
                                    new_date.strftime('%Y-%m-%d'), 
                                    new_heure_str,
                                    duree_pour_db,  # TIME valide
                                    duree_descriptive,  # Durée complète en note
                                    messeur.id
                                ])
                            else:
                                # Sans notes - juste la durée limitée
                                cursor.execute("""
                                    UPDATE captures_messeurtracking 
                                    SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                                    WHERE id = %s
                                """, [
                                    lieu, 
                                    new_date.strftime('%Y-%m-%d'), 
                                    new_heure_str,
                                    duree_pour_db,
                                    messeur.id
                                ])
                                
                            # Stocker la vraie durée pour la réponse
                            duree_response = duree_descriptive
                        else:
                            # Durée normale < 24h
                            cursor.execute("""
                                UPDATE captures_messeurtracking 
                                SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                                WHERE id = %s
                            """, [
                                lieu, 
                                new_date.strftime('%Y-%m-%d'), 
                                new_heure_str,
                                duree_str,
                                messeur.id
                            ])
                            duree_response = duree_str
                    else:
                        # Format invalide
                        duree_str = "00:00:00"
                        duree_response = duree_str
                        cursor.execute("""
                            UPDATE captures_messeurtracking 
                            SET lieu = %s, date_prevu = %s, heure = %s, duree_passage = %s
                            WHERE id = %s
                        """, [
                            lieu, 
                            new_date.strftime('%Y-%m-%d'), 
                            new_heure_str,
                            duree_str,
                            messeur.id
                        ])

                print(f"✅ Sauvegarde avec durée réelle: {duree_response if 'duree_response' in locals() else duree_str}")
                
                # Recharger l'objet
                messeur.refresh_from_db()
                
            except Exception as sql_error:
                print(f"❌ Erreur raw SQL: {sql_error}")
                return Response({
                    'error': f'Erreur sauvegarde SQL: {str(sql_error)}',
                    'debug': {
                        'duree_calculee': duree_str if 'duree_str' in locals() else "N/A",
                        'total_seconds': total_seconds if 'total_seconds' in locals() else 0
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # ENVOYER MISE À JOUR SSE
            update_data = {
                'type': 'position_update',
                'trajet_id': messeur.path.id,
                'tag_rfid': tag_num_serie,
                'objet_nom': f"{messeur.object_tracking.categorie}_{tag_num_serie}",
                'etat_objet': objet.etat,
                'etat_change': previous_lieu != lieu,
                'distances': {
                    'source': round(distance_source, 2),
                    'destination': round(distance_destination, 2)
                },
                'nouvelle_position': {
                    'lieu': lieu,
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': new_date.isoformat(),
                    'heure': new_heure_str,
                    'duree_passage': duree_response if 'duree_response' in locals() else str(messeur.duree_passage)
                }
            }
            
            self.broadcast_sse_update(update_data)
            
            # ====================================================================
            # RÉPONSE AVEC INFORMATIONS SUR LA SÉLECTION DU TRAJET
            # ====================================================================
            response_data = {
                'success': True,
                'message': f'Position mise à jour pour {tag_num_serie}',
                'trajet_id': messeur.path.id,
                'etat_objet': objet.etat,
                'duree_passage': duree_response if 'duree_response' in locals() else str(messeur.duree_passage),
                'distances': update_data['distances'],
                'nouvelle_position': update_data['nouvelle_position'],
                'debug_info': {
                    'timestamp_recu': timestamp,
                    'date_finale': new_date.isoformat(),
                    'heure_finale_string': new_heure_str,
                    'duree_finale_reelle': duree_response if 'duree_response' in locals() else str(messeur.duree_passage),
                    'methode': 'Calcul durée réelle sans limitation'
                }
            }
            
            # Ajouter des informations sur la sélection si plusieurs trajets étaient disponibles
            if messeurs_candidats.count() > 1:
                response_data['selection_info'] = {
                    'trajets_disponibles': messeurs_candidats.count(),
                    'trajet_selectionne': {
                        'path_template_id': messeur.path.id,
                        'nom_trajet': messeur.path.nom,
                        'raison_selection': 'ID PathTemplate le plus petit'
                    },
                    'autres_trajets': [
                        {
                            'path_template_id': m.path.id,
                            'nom_trajet': m.path.nom,
                            'date_debut': m.date_debut.isoformat()
                        }
                        for m in messeurs_candidats.exclude(id=messeur.id)
                    ]
                }
            
            return Response(response_data)
            
        except TagRfid.DoesNotExist:
            return Response({
                'error': f'Tag RFID {tag_num_serie} non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"ERREUR GÉNÉRALE: {str(e)}")
            return Response({
                'error': f'Erreur: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Les autres méthodes restent inchangées...
    def get_current_coordinates(self, messeur):
        """
        Obtenir les coordonnées GPS actuelles du MesseurTracking
        """
        # Essayer d'obtenir les coordonnées depuis les champs directs
        if hasattr(messeur, 'latitude') and hasattr(messeur, 'longitude'):
            if messeur.latitude and messeur.longitude:
                return float(messeur.latitude), float(messeur.longitude)
        
        # Sinon, essayer d'obtenir depuis la dernière position dans l'historique
        derniere_position = PositionHistorique.objects.filter(
            messeur_tracking=messeur
        ).order_by('-timestamp').first()
        
        if derniere_position and derniere_position.latitude and derniere_position.longitude:
            return float(derniere_position.latitude), float(derniere_position.longitude)
        
        # Par défaut, retourner None si pas de coordonnées
        return None, None
    
    def get_location_from_coordinates(self, latitude, longitude):
        """
        Obtenir le nom du lieu à partir des coordonnées GPS en utilisant la géolocalisation inverse
        """
        if not latitude or not longitude:
            return 'Position GPS inconnue'
        
        try:
            geolocation_service = GeolocationService()
            result = geolocation_service.geocoder.reverse_geocode(
                float(latitude), float(longitude)
            )
            
            # Extraire le nom du lieu principal à partir des composants d'adresse
            if result and 'address_components' in result:
                address = result['address_components']
                
                # Prioriser ville > commune > village > quartier
                lieu_parts = []
                
                if 'city' in address:
                    lieu_parts.append(address['city'])
                elif 'town' in address:
                    lieu_parts.append(address['town'])
                elif 'village' in address:
                    lieu_parts.append(address['village'])
                elif 'suburb' in address:
                    lieu_parts.append(address['suburb'])
                elif 'municipality' in address:
                    lieu_parts.append(address['municipality'])
                
                if 'state' in address and len(lieu_parts) > 0:
                    lieu_parts.append(address['state'])
                
                if lieu_parts:
                    lieu = ', '.join(lieu_parts)
                else:
                    # Utiliser le nom formaté et prendre les premiers éléments
                    formatted_address = result.get('formatted_address', '')
                    address_parts = formatted_address.split(',')
                    if len(address_parts) >= 2:
                        lieu = f"{address_parts[0].strip()}, {address_parts[1].strip()}"
                    else:
                        lieu = address_parts[0].strip() if address_parts else f"GPS({latitude}, {longitude})"
                        
                return lieu if lieu else f"GPS({latitude}, {longitude})"
            else:
                return f"GPS({latitude}, {longitude})"
                
        except Exception as e:
            # En cas d'erreur, utiliser les coordonnées
            print(f"Erreur géolocalisation: {str(e)}")
            return f"GPS({latitude}, {longitude})"
    
    def broadcast_sse_update(self, data):
        """
        Fonction pour broadcaster les mises à jour SSE
        """
        # Stocker la mise à jour dans le cache pour les clients SSE
        cache_key = f"sse_update_{data['trajet_id']}"
        cache.set(cache_key, json.dumps(data), 300)  # 5 minutes
        
        # Stocker aussi pour tous les trajets
        cache.set("sse_update_all", json.dumps(data), 300)


class TrajetHistoriqueView2(APIView):
    """
    API pour récupérer l'historique détaillé d'un trajet spécifique
    GET /api/captures/trajet-historique/{id}/
    
    Affiche le trajet complet avec tous les points, position actuelle et statuts
    """
    
    def get(self, request, trajet_id):
        try:
            # Récupérer le PathTemplate
            path_template = PathTemplate.objects.get(id=trajet_id)
            
            # Récupérer le MesseurTracking associé
            messeur = MesseurTracking.objects.select_related(
                'object_tracking', 'capture_rfid'
            ).filter(path=path_template).first()
            
            if not messeur:
                return Response({
                    'error': 'Aucun trajet trouvé avec cet ID'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Informations générales du trajet
            nom_objet = f"{messeur.object_tracking.categorie}_{messeur.capture_rfid.num_serie}"
            
            # Position actuelle depuis MesseurTracking
            position_actuelle = {
                'lieu': messeur.lieu,
                'date_derniere_maj': messeur.date_prevu.isoformat() if messeur.date_prevu else None,
                'heure_derniere_maj': messeur.heure.strftime('%H:%M:%S') if messeur.heure else None
            }
            
            # Obtenir les coordonnées actuelles depuis PositionHistorique
            derniere_position = PositionHistorique.objects.filter(
                messeur_tracking=messeur
            ).order_by('-timestamp').first()
            
            if derniere_position:
                position_actuelle.update({
                    'latitude': derniere_position.latitude,
                    'longitude': derniere_position.longitude,
                    'timestamp_position': derniere_position.timestamp.isoformat()
                })
            
            # Récupérer tous les points du PathTemplate dans l'ordre
            path_points = PathTemplatePoint.objects.filter(
                template=path_template
            ).select_related('point').order_by('ordre')
            
            # Construire la liste des points avec leurs statuts
            points_trajet = []
            
            # 1. Point de départ
            date_entree_depart = self._obtenir_date_entree(messeur, path_template.source)
            point_depart = {
                'id': f'source_{path_template.id}',
                'type': 'source',
                'nom_lieu': path_template.source,
                'latitude': path_template.latitude_src,
                'longitude': path_template.longitude_src,
                'ordre': 0,
                'date_prevu': messeur.date_debut.isoformat(),
                'date_entree': date_entree_depart.date().isoformat() if date_entree_depart else None,
                'heure_entree': date_entree_depart.strftime('%H:%M:%S') if date_entree_depart else None,
                'statut': self._determiner_statut_point(
                    messeur, path_template.source, messeur.date_debut, is_source=True
                ),
                'est_position_actuelle': messeur.lieu == path_template.source
            }
            points_trajet.append(point_depart)
            
            # 2. Points intermédiaires du PathTemplate
            for path_point in path_points:
                date_entree_point = self._obtenir_date_entree(messeur, path_point.point.nom_lieu)
                point_data = {
                    'id': f'point_{path_point.id}',
                    'type': 'intermediate',
                    'nom_lieu': path_point.point.nom_lieu,
                    'latitude': path_point.point.latitude,
                    'longitude': path_point.point.longitude,
                    'ordre': path_point.ordre,
                    'date_prevu': path_point.date_prevu.isoformat() if path_point.date_prevu else None,
                    'date_entree': date_entree_point.date().isoformat() if date_entree_point else None,
                    'heure_entree': date_entree_point.strftime('%H:%M:%S') if date_entree_point else None,
                    'statut': self._determiner_statut_point(
                        messeur, path_point.point.nom_lieu, path_point.date_prevu, is_source=False
                    ),
                    'est_position_actuelle': messeur.lieu == path_point.point.nom_lieu
                }
                points_trajet.append(point_data)
            
            # 3. Point de destination
            date_entree_destination = self._obtenir_date_entree(messeur, path_template.destination)
            point_destination = {
                'id': f'destination_{path_template.id}',
                'type': 'destination',
                'nom_lieu': path_template.destination,
                'latitude': path_template.latitude_dest,
                'longitude': path_template.longitude_dest,
                'ordre': len(path_points) + 1,
                'date_prevu': messeur.date_fin.isoformat(),
                'date_entree': date_entree_destination.date().isoformat() if date_entree_destination else None,
                'heure_entree': date_entree_destination.strftime('%H:%M:%S') if date_entree_destination else None,
                'statut': self._determiner_statut_point(
                    messeur, path_template.destination, messeur.date_fin, is_source=False
                ),
                'est_position_actuelle': messeur.lieu == path_template.destination
            }
            points_trajet.append(point_destination)
            
            # 4. Si la position actuelle n'est dans aucun point défini, l'ajouter
            position_actuelle_dans_liste = any(
                point['est_position_actuelle'] for point in points_trajet
            )
            
            if not position_actuelle_dans_liste and messeur.lieu:
                # Trouver l'ordre approprié pour la position actuelle
                ordre_actuel = self._determiner_ordre_position_actuelle(
                    messeur, points_trajet
                )
                
                # Date d'entrée pour la position actuelle
                date_entree_actuelle = self._obtenir_date_entree(messeur, messeur.lieu)
                
                point_actuel = {
                    'id': f'current_{messeur.id}',
                    'type': 'current_position',
                    'nom_lieu': messeur.lieu,
                    'latitude': derniere_position.latitude if derniere_position else None,
                    'longitude': derniere_position.longitude if derniere_position else None,
                    'ordre': ordre_actuel,
                    'date_prevu': None,
                    'date_entree': date_entree_actuelle.date().isoformat() if date_entree_actuelle else None,
                    'heure_entree': date_entree_actuelle.strftime('%H:%M:%S') if date_entree_actuelle else None,
                    'statut': 'position_actuelle',
                    'est_position_actuelle': True,
                    'date_arrivee': messeur.date_prevu.isoformat() if messeur.date_prevu else None,
                    'heure_arrivee': messeur.heure.strftime('%H:%M:%S') if messeur.heure else None
                }
                
                # Insérer à la bonne position dans la liste
                points_trajet.append(point_actuel)
                points_trajet.sort(key=lambda x: x['ordre'])
            
            # Déterminer l'état dynamique de l'objet
            etat_dynamique = self._determiner_etat_objet(messeur, path_template, points_trajet)
            
            # Statistiques du trajet
            points_arrives = len([p for p in points_trajet if p['statut'] == 'arrive'])
            points_en_retard = len([p for p in points_trajet if p['statut'] == 'arrive_en_retard'])
            points_en_attente = len([p for p in points_trajet if p['statut'] == 'en_attente'])
            
            # Réponse complète
            response_data = {
                'trajet_id': trajet_id,
                'nom_trajet': path_template.nom,
                'objet': {
                    'nom_objet': nom_objet,
                    'etat_actuel': etat_dynamique  # Utiliser l'état dynamique
                },
                'trajet_info': {
                    'lieu_depart': path_template.source,
                    'lieu_destination': path_template.destination,
                    'date_debut': messeur.date_debut.isoformat(),
                    'date_fin_prevue': messeur.date_fin.isoformat(),
                    'coordonnees_depart': {
                        'latitude': path_template.latitude_src,
                        'longitude': path_template.longitude_src
                    },
                    'coordonnees_destination': {
                        'latitude': path_template.latitude_dest,
                        'longitude': path_template.longitude_dest
                    }
                },
                'position_actuelle': position_actuelle,
                'points_trajet': points_trajet,
            }
            
            return Response(response_data)
            
        except PathTemplate.DoesNotExist:
            return Response({
                'error': 'Trajet non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la récupération de l\'historique: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _obtenir_date_entree(self, messeur, nom_lieu):
        """
        Récupère la date d'entrée d'un lieu depuis PositionHistorique
        
        Args:
            messeur: Instance MesseurTracking
            nom_lieu: Nom du lieu à rechercher
            
        Returns:
            datetime: Date d'entrée ou None si pas trouvé
        """
        # Rechercher la date d'entrée dans PositionHistorique
        position_historique = PositionHistorique.objects.filter(
            messeur_tracking=messeur,
            date_entree__isnull=False
        ).filter(
            models.Q(lieu__icontains=nom_lieu) | 
            models.Q(lieu__icontains=nom_lieu.split(',')[0] if ',' in nom_lieu else nom_lieu.split()[0])
        ).order_by('date_entree').first()
        
        if position_historique:
            return position_historique.date_entree
        
        # Si pas trouvé avec correspondance partielle, essayer correspondance inverse
        if messeur.lieu:
            lieu_mots = nom_lieu.lower().split()
            messeur_lieu_lower = messeur.lieu.lower()
            
            # Si l'un des mots du nom du lieu est dans la position actuelle
            for mot in lieu_mots:
                if mot in messeur_lieu_lower:
                    # Chercher la date d'entrée pour la position actuelle
                    position_actuelle_historique = PositionHistorique.objects.filter(
                        messeur_tracking=messeur,
                        lieu=messeur.lieu,
                        date_entree__isnull=False
                    ).order_by('date_entree').first()
                    
                    if position_actuelle_historique:
                        return position_actuelle_historique.date_entree
                    break
        
        return None
    
    def _determiner_etat_objet(self, messeur, path_template, points_trajet):
        """
        Détermine l'état dynamique de l'objet selon sa position dans le trajet
        
        Logique:
        - "recu" : Si l'objet est à la destination finale (PRIORITÉ ABSOLUE)
        - "en_transit" : Si l'objet est entre le départ et la destination
        - "stocke" : Si l'objet est dans un point intermédiaire et y reste
        """
        
        # ============================================================================
        # PRIORITÉ 1: Si l'objet est à la destination finale -> TOUJOURS "recu"
        # ============================================================================
        if messeur.lieu == path_template.destination:
            # Vérification supplémentaire avec correspondance partielle
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
        for point in points_trajet:
            if point['nom_lieu'] in messeur.lieu or messeur.lieu in point['nom_lieu']:
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
        # Par défaut, si l'objet est quelque part entre les points
        # ============================================================================
        return "en_transit"
    
    def _determiner_statut_point(self, messeur, nom_lieu, date_prevu, is_source=False):
        """
        Détermine le statut d'un point basé sur PositionHistorique
        
        LOGIQUE MODIFIÉE: Si c'est la destination ET que l'objet y est -> TOUJOURS "arrive"
        """
        
        # Le point de départ est toujours arrivé
        if is_source:
            return 'arrive'
        
        if not date_prevu:
            return 'en_attente'
        
        # ============================================================================
        # VÉRIFICATION SPÉCIALE POUR LA DESTINATION FINALE
        # ============================================================================
        # Si c'est le point de destination et que l'objet y est actuellement
        if messeur.lieu and nom_lieu:
            lieu_actuel_lower = messeur.lieu.lower()
            nom_lieu_lower = nom_lieu.lower()
            
            # Correspondance pour la destination
            destination_atteinte = False
            
            # Correspondance exacte
            if lieu_actuel_lower == nom_lieu_lower:
                destination_atteinte = True
            
            # Correspondance partielle
            lieu_mots = nom_lieu_lower.split()
            for mot in lieu_mots:
                if len(mot) > 3 and mot in lieu_actuel_lower:
                    destination_atteinte = True
                    break
            
            # Si la destination est atteinte, retourner "arrive" même si en retard
            if destination_atteinte:
                return 'arrive'  # PAS "arrive_en_retard" pour la destination finale
        
        # ============================================================================
        # LOGIQUE STANDARD POUR LES AUTRES POINTS
        # ============================================================================
        # Chercher dans PositionHistorique si l'objet est passé par ce lieu
        position_historique = PositionHistorique.objects.filter(
            messeur_tracking=messeur,
            date_entree__isnull=False
        ).filter(
            models.Q(lieu__icontains=nom_lieu) | 
            models.Q(lieu__icontains=nom_lieu.split(',')[0] if ',' in nom_lieu else nom_lieu.split()[0])
        ).order_by('date_entree').first()
        
        # Vérifier aussi si la position actuelle correspond à cette région
        position_actuelle_correspond = False
        if messeur.lieu:
            # Correspondance plus flexible
            lieu_mots = nom_lieu.lower().split()
            messeur_lieu_lower = messeur.lieu.lower()
            
            # Si l'un des mots du nom du lieu est dans la position actuelle
            for mot in lieu_mots:
                if mot in messeur_lieu_lower:
                    position_actuelle_correspond = True
                    break
        
        # Si on trouve une correspondance dans l'historique OU si la position actuelle correspond
        if position_historique or position_actuelle_correspond:
            # Si on a un historique précis, utiliser sa date
            if position_historique and position_historique.date_entree:
                date_entree = position_historique.date_entree.date()
                
                if isinstance(date_prevu, str):
                    from datetime import datetime
                    date_prevu = datetime.fromisoformat(date_prevu).date()
                
                if date_entree <= date_prevu:
                    return 'arrive'
                else:
                    return 'arrive_en_retard'
            
            # Si pas d'historique mais position actuelle correspond
            elif position_actuelle_correspond:
                # Utiliser la date actuelle pour la comparaison
                date_actuelle = date.today()
                
                if isinstance(date_prevu, str):
                    from datetime import datetime
                    date_prevu = datetime.fromisoformat(date_prevu).date()
                
                if date_actuelle <= date_prevu:
                    return 'arrive'
                else:
                    return 'arrive_en_retard'
        
        # Le point n'existe pas encore dans l'historique et position actuelle ne correspond pas
        return 'en_attente'
    

    
    def _determiner_ordre_position_actuelle(self, messeur, points_trajet):
        """
        Détermine l'ordre approprié pour insérer la position actuelle
        basé sur l'historique chronologique des positions
        """
        # Si la position actuelle correspond exactement à un point existant, utiliser son ordre
        for point in points_trajet:
            if point['nom_lieu'] == messeur.lieu:
                return point['ordre']
        
        # Obtenir tous les lieux visités dans l'ordre chronologique depuis PositionHistorique
        positions_visitees = PositionHistorique.objects.filter(
            messeur_tracking=messeur,
            date_entree__isnull=False
        ).order_by('date_entree').values_list('lieu', flat=True)
        
        if not positions_visitees:
            # Si pas d'historique, placer au début
            return 0.5
        
        # Trouver le dernier point du trajet que l'objet a visité
        dernier_point_visite_ordre = -1
        
        for position_visitee in positions_visitees:
            for point in points_trajet:
                # Vérifier si la position visitée correspond à un point du trajet
                if (point['nom_lieu'].lower() in position_visitee.lower() or 
                    position_visitee.lower() in point['nom_lieu'].lower()):
                    # Mettre à jour le dernier point visité si c'est plus récent
                    if point['ordre'] > dernier_point_visite_ordre:
                        dernier_point_visite_ordre = point['ordre']
        
        # Si on a trouvé un point visité, placer la position actuelle juste après
        if dernier_point_visite_ordre >= 0:
            return dernier_point_visite_ordre + 0.1
        
        # Sinon, essayer de déterminer la position logique
        # Basé sur la distance géographique ou l'ordre des points
        if points_trajet:
            # Trouver le point le plus proche géographiquement de la position actuelle
            derniere_position = PositionHistorique.objects.filter(
                messeur_tracking=messeur
            ).order_by('-timestamp').first()
            
            if derniere_position:
                position_actuelle_lat = derniere_position.latitude
                position_actuelle_lon = derniere_position.longitude
                
                distances = []
                for point in points_trajet:
                    if point['latitude'] and point['longitude']:
                        # Calcul simple de distance (approximatif)
                        distance = ((point['latitude'] - position_actuelle_lat) ** 2 + 
                                  (point['longitude'] - position_actuelle_lon) ** 2) ** 0.5
                        distances.append((distance, point['ordre']))
                
                if distances:
                    # Trier par distance et prendre le point le plus proche
                    distances.sort()
                    point_proche_ordre = distances[0][1]
                    return point_proche_ordre + 0.1
        
        # Par défaut, placer au milieu
        return len(points_trajet) / 2
    
class TrajetHistoriqueView(APIView):
    """
    API pour récupérer l'historique détaillé d'un trajet spécifique
    GET /api/captures/trajet-historique/{id}/
    
    Affiche le trajet complet avec tous les points, position actuelle et statuts
    """
    
    def get(self, request, trajet_id):
        try:
            # Récupérer le PathTemplate
            path_template = PathTemplate.objects.get(id=trajet_id)
            
            # Récupérer le MesseurTracking associé
            messeur = MesseurTracking.objects.select_related(
                'object_tracking', 'capture_rfid'
            ).filter(path=path_template).first()
            
            if not messeur:
                return Response({
                    'error': 'Aucun trajet trouvé avec cet ID'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Informations générales du trajet
            nom_objet = f"{messeur.object_tracking.categorie}_{messeur.capture_rfid.num_serie}"
            
            # Position actuelle depuis MesseurTracking
            position_actuelle = {
                'lieu': messeur.lieu,
                'date_derniere_maj': messeur.date_prevu.isoformat() if messeur.date_prevu else None,
                'heure_derniere_maj': messeur.heure.strftime('%H:%M:%S') if messeur.heure else None
            }
            
            # Obtenir les coordonnées actuelles depuis PositionHistorique
            derniere_position = PositionHistorique.objects.filter(
                messeur_tracking=messeur
            ).order_by('-timestamp').first()
            
            if derniere_position:
                position_actuelle.update({
                    'latitude': derniere_position.latitude,
                    'longitude': derniere_position.longitude,
                    'timestamp_position': derniere_position.timestamp.isoformat()
                })
            
            # Récupérer tous les points du PathTemplate dans l'ordre
            path_points = PathTemplatePoint.objects.filter(
                template=path_template
            ).select_related('point').order_by('ordre')
            
            # Construire la liste des points avec leurs statuts
            points_trajet = []
            
            # 1. Point de départ
            date_entree_depart = self._obtenir_date_entree(messeur, path_template.source)
            point_depart = {
                'id': f'source_{path_template.id}',
                'type': 'source',
                'nom_lieu': path_template.source,
                'latitude': path_template.latitude_src,
                'longitude': path_template.longitude_src,
                'ordre': 0,
                'date_prevu': messeur.date_debut.isoformat(),
                'date_entree': date_entree_depart.date().isoformat() if date_entree_depart else None,
                'heure_entree': date_entree_depart.strftime('%H:%M:%S') if date_entree_depart else None,
                'statut': self._determiner_statut_point(
                    messeur, path_template.source, messeur.date_debut, is_source=True
                ),
                'est_position_actuelle': messeur.lieu == path_template.source
            }
            points_trajet.append(point_depart)
            
            # 2. Points intermédiaires du PathTemplate
            for path_point in path_points:
                date_entree_point = self._obtenir_date_entree(messeur, path_point.point.nom_lieu)
                point_data = {
                    'id': f'point_{path_point.id}',
                    'type': 'intermediate',
                    'nom_lieu': path_point.point.nom_lieu,
                    'latitude': path_point.point.latitude,
                    'longitude': path_point.point.longitude,
                    'ordre': path_point.ordre,
                    'date_prevu': path_point.date_prevu.isoformat() if path_point.date_prevu else None,
                    'date_entree': date_entree_point.date().isoformat() if date_entree_point else None,
                    'heure_entree': date_entree_point.strftime('%H:%M:%S') if date_entree_point else None,
                    'statut': self._determiner_statut_point(
                        messeur, path_point.point.nom_lieu, path_point.date_prevu, is_source=False
                    ),
                    'est_position_actuelle': messeur.lieu == path_point.point.nom_lieu
                }
                points_trajet.append(point_data)
            
            # 3. Point de destination
            date_entree_destination = self._obtenir_date_entree(messeur, path_template.destination)
            point_destination = {
                'id': f'destination_{path_template.id}',
                'type': 'destination',
                'nom_lieu': path_template.destination,
                'latitude': path_template.latitude_dest,
                'longitude': path_template.longitude_dest,
                'ordre': len(path_points) + 1,
                'date_prevu': messeur.date_fin.isoformat(),
                'date_entree': date_entree_destination.date().isoformat() if date_entree_destination else None,
                'heure_entree': date_entree_destination.strftime('%H:%M:%S') if date_entree_destination else None,
                'statut': self._determiner_statut_point(
                    messeur, path_template.destination, messeur.date_fin, is_source=False
                ),
                'est_position_actuelle': messeur.lieu == path_template.destination
            }
            points_trajet.append(point_destination)
            
            # 4. Si la position actuelle n'est dans aucun point défini, l'ajouter
            position_actuelle_dans_liste = any(
                point['est_position_actuelle'] for point in points_trajet
            )
            
            if not position_actuelle_dans_liste and messeur.lieu:
                # Trouver l'ordre approprié pour la position actuelle
                ordre_actuel = self._determiner_ordre_position_actuelle(
                    messeur, points_trajet
                )
                
                # Date d'entrée pour la position actuelle
                date_entree_actuelle = self._obtenir_date_entree(messeur, messeur.lieu)
                
                point_actuel = {
                    'id': f'current_{messeur.id}',
                    'type': 'current_position',
                    'nom_lieu': messeur.lieu,
                    'latitude': derniere_position.latitude if derniere_position else None,
                    'longitude': derniere_position.longitude if derniere_position else None,
                    'ordre': ordre_actuel,
                    'date_prevu': None,
                    'date_entree': date_entree_actuelle.date().isoformat() if date_entree_actuelle else None,
                    'heure_entree': date_entree_actuelle.strftime('%H:%M:%S') if date_entree_actuelle else None,
                    'statut': 'position_actuelle',
                    'est_position_actuelle': True,
                    'date_arrivee': messeur.date_prevu.isoformat() if messeur.date_prevu else None,
                    'heure_arrivee': messeur.heure.strftime('%H:%M:%S') if messeur.heure else None
                }
                
                # Insérer à la bonne position dans la liste
                points_trajet.append(point_actuel)
                points_trajet.sort(key=lambda x: x['ordre'])
            
            # Déterminer l'état dynamique de l'objet
            etat_dynamique = self._determiner_etat_objet(messeur, path_template, points_trajet)
            
            # Réponse complète
            response_data = {
                'trajet_id': trajet_id,
                'nom_trajet': path_template.nom,
                'objet': {
                    'nom_objet': nom_objet,
                    'etat_actuel': etat_dynamique
                },
                'trajet_info': {
                    'lieu_depart': path_template.source,
                    'lieu_destination': path_template.destination,
                    'date_debut': messeur.date_debut.isoformat(),
                    'date_fin_prevue': messeur.date_fin.isoformat(),
                    'coordonnees_depart': {
                        'latitude': path_template.latitude_src,
                        'longitude': path_template.longitude_src
                    },
                    'coordonnees_destination': {
                        'latitude': path_template.latitude_dest,
                        'longitude': path_template.longitude_dest
                    }
                },
                'position_actuelle': position_actuelle,
                'points_trajet': points_trajet,
            }
            
            return Response(response_data)
            
        except PathTemplate.DoesNotExist:
            return Response({
                'error': 'Trajet non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la récupération de l\'historique: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _obtenir_date_entree(self, messeur, nom_lieu):
        """
        Récupère la date d'entrée d'un lieu depuis PositionHistorique
        """
        position_historique = PositionHistorique.objects.filter(
            messeur_tracking=messeur,
            date_entree__isnull=False
        ).filter(
            models.Q(lieu__icontains=nom_lieu) | 
            models.Q(lieu__icontains=nom_lieu.split(',')[0] if ',' in nom_lieu else nom_lieu.split()[0])
        ).order_by('date_entree').first()
        
        if position_historique:
            return position_historique.date_entree
        
        if messeur.lieu:
            lieu_mots = nom_lieu.lower().split()
            messeur_lieu_lower = messeur.lieu.lower()
            
            for mot in lieu_mots:
                if mot in messeur_lieu_lower:
                    position_actuelle_historique = PositionHistorique.objects.filter(
                        messeur_tracking=messeur,
                        lieu=messeur.lieu,
                        date_entree__isnull=False
                    ).order_by('date_entree').first()
                    
                    if position_actuelle_historique:
                        return position_actuelle_historique.date_entree
                    break
        
        return None
    
    def _determiner_etat_objet(self, messeur, path_template, points_trajet):
        """
        Détermine l'état dynamique de l'objet selon sa position dans le trajet
        """
        if messeur.lieu and path_template.destination:
            lieu_destination = path_template.destination.lower()
            lieu_actuel = messeur.lieu.lower()
            
            if lieu_destination == lieu_actuel:
                return "reçu"
            
            destination_mots = lieu_destination.split()
            for mot in destination_mots:
                if len(mot) > 3 and mot in lieu_actuel:
                    return "reçu"
            
            actuel_mots = lieu_actuel.split()
            for mot in actuel_mots:
                if len(mot) > 3 and mot in lieu_destination:
                    return "reçu"
        
        if path_template.destination:
            destination_atteinte = PositionHistorique.objects.filter(
                messeur_tracking=messeur,
                lieu__icontains=path_template.destination.split(',')[0] if ',' in path_template.destination else path_template.destination.split()[0]
            ).exists()
            
            if destination_atteinte:
                return "reçu"
        
        if messeur.lieu == path_template.source:
            positions_apres_depart = PositionHistorique.objects.filter(
                messeur_tracking=messeur
            ).exclude(lieu=path_template.source).exists()
            
            if positions_apres_depart:
                return "en_transit"
            else:
                return "stocke"
        
        for point in points_trajet:
            if point['nom_lieu'] in messeur.lieu or messeur.lieu in point['nom_lieu']:
                derniere_position = PositionHistorique.objects.filter(
                    messeur_tracking=messeur,
                    lieu=messeur.lieu
                ).order_by('-timestamp').first()
                
                if derniere_position and derniere_position.date_entree:
                    temps_dans_lieu = datetime.now() - derniere_position.date_entree.replace(tzinfo=None)
                    
                    if temps_dans_lieu > timedelta(hours=24):
                        return "stocke"
                    else:
                        return "en_transit"
                
                return "en_transit"
        
        return "en_transit"
    
    def _determiner_statut_point(self, messeur, nom_lieu, date_prevu, is_source=False):
        """
        Détermine le statut d'un point basé sur PositionHistorique
        
        CORRECTION: Bien gérer les retards pour tous les points (pas seulement destination)
        """
        
        # Le point de départ est toujours arrivé
        if is_source:
            return 'arrive'
        
        if not date_prevu:
            return 'en_attente'
        
        # ============================================================================
        # VÉRIFICATION SPÉCIALE POUR LA DESTINATION FINALE
        # ============================================================================
        # Si c'est le point de destination et que l'objet y est actuellement
        if messeur.lieu and nom_lieu:
            lieu_actuel_lower = messeur.lieu.lower()
            nom_lieu_lower = nom_lieu.lower()
            
            # Correspondance pour la destination
            destination_atteinte = False
            
            # Correspondance exacte
            if lieu_actuel_lower == nom_lieu_lower:
                destination_atteinte = True
            
            # Correspondance partielle
            lieu_mots = nom_lieu_lower.split()
            for mot in lieu_mots:
                if len(mot) > 3 and mot in lieu_actuel_lower:
                    destination_atteinte = True
                    break
            
            # Si la destination est atteinte, vérifier quand même s'il y a retard
            if destination_atteinte:
                # CORRECTION: Vérifier le retard même pour la destination finale
                if messeur.date_prevu:
                    date_arrivee_reelle = messeur.date_prevu
                else:
                    date_arrivee_reelle = date.today()
                
                if isinstance(date_prevu, str):
                    from datetime import datetime
                    date_prevu_obj = datetime.fromisoformat(date_prevu).date()
                else:
                    date_prevu_obj = date_prevu
                
                #  RETOURNER "arrive_en_retard" si en retard, même pour la destination
                if date_arrivee_reelle > date_prevu_obj:
                    return 'arrive_en_retard'
                else:
                    return 'arrive'
        
        # ============================================================================
        # LOGIQUE STANDARD POUR LES AUTRES POINTS
        # ============================================================================
        # Chercher dans PositionHistorique si l'objet est passé par ce lieu
        position_historique = PositionHistorique.objects.filter(
            messeur_tracking=messeur,
            date_entree__isnull=False
        ).filter(
            models.Q(lieu__icontains=nom_lieu) | 
            models.Q(lieu__icontains=nom_lieu.split(',')[0] if ',' in nom_lieu else nom_lieu.split()[0])
        ).order_by('date_entree').first()
        
        # Vérifier aussi si la position actuelle correspond à cette région
        position_actuelle_correspond = False
        if messeur.lieu:
            # Correspondance plus flexible
            lieu_mots = nom_lieu.lower().split()
            messeur_lieu_lower = messeur.lieu.lower()
            
            # Si l'un des mots du nom du lieu est dans la position actuelle
            for mot in lieu_mots:
                if len(mot) > 3 and mot in messeur_lieu_lower:  # Mots de plus de 3 caractères
                    position_actuelle_correspond = True
                    break
        
        # Si on trouve une correspondance dans l'historique OU si la position actuelle correspond
        if position_historique or position_actuelle_correspond:
            # Si on a un historique précis, utiliser sa date
            if position_historique and position_historique.date_entree:
                date_entree = position_historique.date_entree.date()
                
                if isinstance(date_prevu, str):
                    from datetime import datetime
                    date_prevu_obj = datetime.fromisoformat(date_prevu).date()
                else:
                    date_prevu_obj = date_prevu
                
                #  CORRECTION: Comparaison correcte pour détecter les retards
                if date_entree <= date_prevu_obj:
                    return 'arrive'
                else:
                    return 'arrive_en_retard'  # En retard !
            
            # Si pas d'historique mais position actuelle correspond
            elif position_actuelle_correspond:
                #  CORRECTION: Utiliser la date de la dernière mise à jour du messeur
                if messeur.date_prevu:
                    date_arrivee_reelle = messeur.date_prevu
                else:
                    date_arrivee_reelle = date.today()
                
                if isinstance(date_prevu, str):
                    from datetime import datetime
                    date_prevu_obj = datetime.fromisoformat(date_prevu).date()
                else:
                    date_prevu_obj = date_prevu
                
                # CORRECTION: Détecter le retard pour tous les points
                if date_arrivee_reelle <= date_prevu_obj:
                    return 'arrive'
                else:
                    return 'arrive_en_retard'  # En retard !
        
        # Le point n'existe pas encore dans l'historique et position actuelle ne correspond pas
        return 'en_attente'
    
    def _determiner_ordre_position_actuelle(self, messeur, points_trajet):
        """
        Détermine l'ordre approprié pour insérer la position actuelle
        basé sur l'historique chronologique des positions
        """
        for point in points_trajet:
            if point['nom_lieu'] == messeur.lieu:
                return point['ordre']
        
        positions_visitees = PositionHistorique.objects.filter(
            messeur_tracking=messeur,
            date_entree__isnull=False
        ).order_by('date_entree').values_list('lieu', flat=True)
        
        if not positions_visitees:
            return 0.5
        
        dernier_point_visite_ordre = -1
        
        for position_visitee in positions_visitees:
            for point in points_trajet:
                if (point['nom_lieu'].lower() in position_visitee.lower() or 
                    position_visitee.lower() in point['nom_lieu'].lower()):
                    if point['ordre'] > dernier_point_visite_ordre:
                        dernier_point_visite_ordre = point['ordre']
        
        if dernier_point_visite_ordre >= 0:
            return dernier_point_visite_ordre + 0.1
        
        if points_trajet:
            derniere_position = PositionHistorique.objects.filter(
                messeur_tracking=messeur
            ).order_by('-timestamp').first()
            
            if derniere_position:
                position_actuelle_lat = derniere_position.latitude
                position_actuelle_lon = derniere_position.longitude
                
                distances = []
                for point in points_trajet:
                    if point['latitude'] and point['longitude']:
                        distance = ((point['latitude'] - position_actuelle_lat) ** 2 + 
                                  (point['longitude'] - position_actuelle_lon) ** 2) ** 0.5
                        distances.append((distance, point['ordre']))
                
                if distances:
                    distances.sort()
                    point_proche_ordre = distances[0][1]
                    return point_proche_ordre + 0.1
        
        return len(points_trajet) / 2
    
def trajet_sse_stream(request, trajet_id=None):
    """
    SSE Stream sans heartbeat - Version simplifiée
    """
    def stream_real_database_data():
        while True:
            try:
                if trajet_id:
                    trajets = PathTemplate.objects.filter(id=trajet_id)
                else:
                    trajets = PathTemplate.objects.all()

                for trajet in trajets:
                    try:
                        messeur = MesseurTracking.objects.filter(path=trajet).first()
                        if messeur:
                            # Vérifier les mises à jour en cache
                            if trajet_id:
                                cache_key = f"sse_update_{trajet_id}"
                                cache_update = cache.get(cache_key)
                                if cache_update:
                                    yield f"data: {cache_update}\n\n"
                                    cache.delete(cache_key)
                                    continue

                            # Obtenir les données réelles
                            latest_position = PositionHistorique.objects.filter(
                                messeur_tracking=messeur
                            ).order_by('-timestamp').first()

                            if latest_position:
                                current_lat = latest_position.latitude
                                current_lng = latest_position.longitude
                                lieu_actuel = latest_position.lieu
                            else:
                                current_lat = trajet.latitude_src or 0.0
                                current_lng = trajet.longitude_src or 0.0
                                lieu_actuel = messeur.lieu or trajet.source

                            # Format TrajetList
                            trajet_data = {
                                'type': 'trajet_update',
                                'id': trajet.id,
                                'nom_trajet': str(trajet.nom) if trajet.nom else f"Trajet {trajet.id}",
                                'objet_nom': f"{messeur.object_tracking.categorie}_{messeur.capture_rfid.num_serie}",
                                'capteur_num_serie': str(messeur.capture_rfid.num_serie),
                                'etat_objet': messeur.object_tracking.etat,
                                'localisation_actuelle': lieu_actuel,
                                'latitude_actuelle': round(float(current_lat), 6),
                                'longitude_actuelle': round(float(current_lng), 6),
                                'derniere_mise_a_jour': messeur.date_prevu.isoformat() if messeur.date_prevu else datetime.now().date().isoformat(),
                                'heure_derniere_mise_a_jour': messeur.heure.strftime('%H:%M:%S') if messeur.heure else datetime.now().time().strftime('%H:%M:%S'),
                                'lien_historique': f'/api/captures/trajet-historique/{trajet.id}/',
                                'timestamp': datetime.now().isoformat()
                            }

                            yield f"data: {json.dumps(trajet_data)}\n\n"

                    except Exception as e:
                        error_data = {
                            'type': 'error',
                            'message': str(e),
                            'timestamp': datetime.now().isoformat()
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"

                time.sleep(2)  # Mise à jour toutes les 2 secondes

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                time.sleep(5)

    response = StreamingHttpResponse(stream_real_database_data(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response




def trajet_stream_all(request, trajet_id=None):
    """
    SSE Stream qui retourne tous les trajets en une seule fois sous forme de tableau
    """
    def stream_all_trajets_data():
        while True:
            try:
                if trajet_id:
                    trajets = PathTemplate.objects.filter(id=trajet_id)
                else:
                    trajets = PathTemplate.objects.all()

                # Collecter toutes les données des trajets dans un tableau
                all_trajets_data = []

                for trajet in trajets:
                    try:
                        messeur = MesseurTracking.objects.filter(path=trajet).first()
                        if messeur:
                            # Vérifier les mises à jour en cache pour ce trajet spécifique
                            cache_key = f"sse_update_{trajet.id}"
                            cache_update = cache.get(cache_key)
                            
                            if cache_update:
                                # Si une mise à jour en cache existe, l'utiliser
                                try:
                                    cached_data = json.loads(cache_update) if isinstance(cache_update, str) else cache_update
                                    
                                    # CORRECTION: Récupérer les coordonnées depuis le cache ou la nouvelle position
                                    if 'nouvelle_position' in cached_data:
                                        current_lat = cached_data['nouvelle_position'].get('latitude')
                                        current_lng = cached_data['nouvelle_position'].get('longitude')
                                        lieu_actuel = cached_data['nouvelle_position'].get('lieu')
                                    else:
                                        current_lat = cached_data.get('latitude_actuelle')
                                        current_lng = cached_data.get('longitude_actuelle')
                                        lieu_actuel = cached_data.get('localisation_actuelle')
                                    
                                    trajet_data = {
                                        'id': trajet.id,
                                        'nom_trajet': str(trajet.nom) if trajet.nom else f"Trajet {trajet.id}",
                                        'objet_nom': f"{messeur.object_tracking.categorie}_{messeur.capture_rfid.num_serie}",
                                        'capteur_num_serie': str(messeur.capture_rfid.num_serie),
                                        'etat_objet': cached_data.get('etat_objet', messeur.object_tracking.etat),
                                        'localisation_actuelle': lieu_actuel or messeur.lieu,
                                        'latitude_actuelle': float(current_lat) if current_lat is not None else None,
                                        'longitude_actuelle': float(current_lng) if current_lng is not None else None,
                                        'derniere_mise_a_jour': messeur.date_prevu.isoformat() if messeur.date_prevu else datetime.now().date().isoformat(),
                                        'heure_derniere_mise_a_jour': messeur.heure.strftime('%H:%M:%S') if messeur.heure else datetime.now().time().strftime('%H:%M:%S'),
                                        'lien_historique': f"{request.build_absolute_uri('/')[:-1]}/api/captures/trajet-historique/{trajet.id}/"
                                    }
                                    cache.delete(cache_key)  # Supprimer après utilisation
                                except Exception as e:
                                    print(f"Erreur parsing cache: {e}")
                                    trajet_data = None
                            else:
                                trajet_data = None

                            # CORRECTION: Si pas de données du cache, récupérer depuis la base de données
                            if trajet_data is None:
                                # Obtenir les coordonnées depuis PositionHistorique
                                latest_position = PositionHistorique.objects.filter(
                                    messeur_tracking=messeur
                                ).order_by('-timestamp').first()

                                # CORRECTION: Récupérer AUSSI depuis MesseurTracking si disponible
                                current_lat = None
                                current_lng = None
                                lieu_actuel = messeur.lieu

                                # Priorité 1: Coordonnées depuis MesseurTracking
                                if hasattr(messeur, 'latitude') and hasattr(messeur, 'longitude'):
                                    if messeur.latitude is not None and messeur.longitude is not None:
                                        current_lat = float(messeur.latitude)
                                        current_lng = float(messeur.longitude)
                                        print(f"Coordonnées depuis MesseurTracking: {current_lat}, {current_lng}")

                                # Priorité 2: Coordonnées depuis PositionHistorique
                                if (current_lat is None or current_lng is None) and latest_position:
                                    if latest_position.latitude is not None and latest_position.longitude is not None:
                                        current_lat = float(latest_position.latitude)
                                        current_lng = float(latest_position.longitude)
                                        lieu_actuel = latest_position.lieu
                                        print(f"Coordonnées depuis PositionHistorique: {current_lat}, {current_lng}")

                                # Priorité 3: Coordonnées par défaut du trajet
                                if current_lat is None or current_lng is None:
                                    if trajet.latitude_src is not None and trajet.longitude_src is not None:
                                        current_lat = float(trajet.latitude_src)
                                        current_lng = float(trajet.longitude_src)
                                        lieu_actuel = trajet.source
                                        print(f"Coordonnées par défaut: {current_lat}, {current_lng}")

                                # Utiliser la même logique que TrajetListSerializer pour l'état
                                etat_objet = _determiner_etat_objet_sse(messeur, trajet)

                                trajet_data = {
                                    'id': trajet.id,
                                    'nom_trajet': str(trajet.nom) if trajet.nom else f"Trajet {trajet.id}",
                                    'objet_nom': f"{messeur.object_tracking.categorie}_{messeur.capture_rfid.num_serie}",
                                    'capteur_num_serie': str(messeur.capture_rfid.num_serie),
                                    'etat_objet': etat_objet,
                                    'localisation_actuelle': lieu_actuel,
                                    'latitude_actuelle': current_lat,  # Ne pas arrondir si None
                                    'longitude_actuelle': current_lng,  # Ne pas arrondir si None
                                    'derniere_mise_a_jour': messeur.date_prevu.isoformat() if messeur.date_prevu else datetime.now().date().isoformat(),
                                    'heure_derniere_mise_a_jour': messeur.heure.strftime('%H:%M:%S') if messeur.heure else datetime.now().time().strftime('%H:%M:%S'),
                                    'lien_historique': f"{request.build_absolute_uri('/')[:-1]}/api/captures/trajet-historique/{trajet.id}/"
                                }

                                # Debug pour voir les valeurs finales
                                print(f"Trajet {trajet.id} - Coordonnées finales: lat={current_lat}, lng={current_lng}, lieu={lieu_actuel}")

                            all_trajets_data.append(trajet_data)

                    except Exception as e:
                        print(f"Erreur pour trajet {trajet.id}: {e}")
                        # En cas d'erreur pour un trajet, ajouter une entrée d'erreur
                        error_trajet = {
                            'id': trajet.id,
                            'nom_trajet': f"Erreur - Trajet {trajet.id}",
                            'objet_nom': "Erreur",
                            'capteur_num_serie': "N/A",
                            'etat_objet': "erreur",
                            'localisation_actuelle': f"Erreur: {str(e)}",
                            'latitude_actuelle': None,
                            'longitude_actuelle': None,
                            'derniere_mise_a_jour': datetime.now().date().isoformat(),
                            'heure_derniere_mise_a_jour': datetime.now().time().strftime('%H:%M:%S'),
                            'lien_historique': f"{request.build_absolute_uri('/')[:-1]}/api/captures/trajet-historique/{trajet.id}/"
                        }
                        all_trajets_data.append(error_trajet)

                # Envoyer toutes les données en une seule fois
                if all_trajets_data:
                    response_data = {
                        'type': 'trajets_batch_update',
                        'timestamp': datetime.now().isoformat(),
                        'total_trajets': len(all_trajets_data),
                        'trajets': all_trajets_data
                    }
                    yield f"data: {json.dumps(response_data)}\n\n"
                else:
                    # Si aucun trajet trouvé
                    empty_response = {
                        'type': 'trajets_batch_update',
                        'timestamp': datetime.now().isoformat(),
                        'total_trajets': 0,
                        'trajets': []
                    }
                    yield f"data: {json.dumps(empty_response)}\n\n"

                time.sleep(2)  # Mise à jour toutes les 2 secondes

            except Exception as e:
                print(f"Erreur générale stream: {e}")
                error_response = {
                    'type': 'error',
                    'message': str(e),
                    'timestamp': datetime.now().isoformat(),
                    'trajets': []
                }
                yield f"data: {json.dumps(error_response)}\n\n"
                time.sleep(5)

    response = StreamingHttpResponse(stream_all_trajets_data(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    
    return response

def _determiner_etat_objet_sse(messeur, trajet):
    """
    Fonction helper pour déterminer l'état de l'objet dans SSE
    Utilise la même logique que TrajetHistoriqueView._determiner_etat_objet
    """
    
    
    # ============================================================================
    # PRIORITÉ 1: Si l'objet est à la destination finale -> TOUJOURS "recu"
    # ============================================================================
    if messeur.lieu and trajet.destination:
        lieu_destination = trajet.destination.lower()
        lieu_actuel = messeur.lieu.lower()
        
        # Correspondance exacte
        if lieu_destination == lieu_actuel:
            return "reçu"
        
        # Correspondance partielle
        destination_mots = lieu_destination.split()
        for mot in destination_mots:
            if len(mot) > 3 and mot in lieu_actuel:
                return "reçu"
        
        # Correspondance inverse
        actuel_mots = lieu_actuel.split()
        for mot in actuel_mots:
            if len(mot) > 3 and mot in lieu_destination:
                return "reçu"
    
    # Vérifier dans l'historique
    if trajet.destination:
        destination_atteinte = PositionHistorique.objects.filter(
            messeur_tracking=messeur,
            lieu__icontains=trajet.destination.split(',')[0] if ',' in trajet.destination else trajet.destination.split()[0]
        ).exists()
        
        if destination_atteinte:
            return "reçu"
    
    # ============================================================================
    # PRIORITÉ 2: Si l'objet est au point de départ
    # ============================================================================
    if messeur.lieu == trajet.source:
        positions_apres_depart = PositionHistorique.objects.filter(
            messeur_tracking=messeur
        ).exclude(lieu=trajet.source).exists()
        
        if positions_apres_depart:
            return "en_transit"
        else:
            return "stocke"
    
    # ============================================================================
    # Vérifier si l'objet est perdu (pas de mise à jour récente)
    # ============================================================================
    if messeur.date_prevu and messeur.heure:
        last_update = datetime.combine(messeur.date_prevu, messeur.heure)
        time_diff = (datetime.now() - last_update).total_seconds()
        
        if time_diff > 172800:  # Plus de 48 heures sans signal
            return 'perdu'
    
    # Par défaut
    return "en_transit"

class GeocodeAddressView(APIView):
    """
    API pour convertir une adresse en coordonnées
    POST /api/captures/geocode/
    """
    
    def post(self, request, *args, **kwargs):
        address = request.data.get('address')
        if not address:
            return Response({'error': 'Adresse requise'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            geolocation_service = GeolocationService()
            result = geolocation_service.process_location(address)
            
            return Response({
                'success': True,
                'result': result
            })
            
        except ValidationError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ReverseGeocodeView(APIView):
    """
    API pour convertir des coordonnées en adresse
    POST /api/captures/reverse-geocode/
    """
    
    def post(self, request, *args, **kwargs):
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if latitude is None or longitude is None:
            return Response({
                'error': 'Latitude et longitude requises'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            geolocation_service = GeolocationService()
            result = geolocation_service.geocoder.reverse_geocode(latitude, longitude)
            
            return Response({
                'success': True,
                'result': result
            })
            
        except ValidationError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class SearchPlacesView(APIView):
    """
    API pour rechercher des lieux
    GET /api/captures/search-places/?q=query&limit=5
    """
    
    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q')
        limit = int(request.query_params.get('limit', 5))
        
        if not query:
            return Response({'error': 'Paramètre de recherche requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            geolocation_service = GeolocationService()
            results = geolocation_service.search_places(query, limit)
            
            return Response({
                'success': True,
                'results': results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckObjetStatusView(APIView):
    """
    API pour vérifier et mettre à jour le statut de tous les objets
    POST /api/captures/check-objet-status/
    """
    
    def post(self, request):
        
        
        updated_objects = []
        
        try:
            # Récupérer tous les trajets actifs
            messeurs = MesseurTracking.objects.select_related('object_tracking', 'path').all()
            
            for messeur in messeurs:
                objet = messeur.object_tracking
                path = messeur.path
                previous_etat = objet.etat
                
                # Vérifier si l'objet est perdu
                if messeur.date_prevu and messeur.heure:
                    last_update = datetime.combine(messeur.date_prevu, messeur.heure)
                    time_diff = (datetime.now() - last_update).total_seconds()
                    
                    if time_diff > 7200:  # Plus de 2 heures
                        objet.etat = 'perdu'
                    elif messeur.lieu == path.source:
                        objet.etat = 'stocke'
                    elif messeur.lieu == path.destination:
                        objet.etat = 'arrive'
                    else:
                        objet.etat = 'en_transit'
                
                # Sauvegarder si l'état a changé
                if objet.etat != previous_etat:
                    objet.save()
                    updated_objects.append({
                        'objet_nom': f"{objet.categorie}_{messeur.capture_rfid.num_serie}",
                        'ancien_etat': previous_etat,
                        'nouvel_etat': objet.etat,
                        'lieu_actuel': messeur.lieu,
                        'derniere_mise_a_jour': messeur.date_prevu.isoformat() if messeur.date_prevu else None
                    })
            
            return Response({
                'success': True,
                'message': f'{len(updated_objects)} objets mis à jour',
                'objets_modifies': updated_objects
            })
            
        except Exception as e:
            return Response({
                'error': f'Erreur lors de la vérification: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)