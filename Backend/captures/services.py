# captures/services.py
import requests
import time
from rest_framework.exceptions import ValidationError
import math
from django.conf import settings
from django.core.cache import cache


class NominatimGeocoder:
    """
    Service de géocodage utilisant Nominatim (OpenStreetMap) - GRATUIT
    """
    
    def __init__(self):
        geo_settings = getattr(settings, 'GEOLOCATION_SETTINGS', {})
        
        self.base_url = geo_settings.get('NOMINATIM_BASE_URL', 'https://nominatim.openstreetmap.org')
        self.user_agent = geo_settings.get('NOMINATIM_USER_AGENT', 'M-IoT Backend/1.0')
        self.delay = geo_settings.get('NOMINATIM_DELAY', 1)
        self.timeout = geo_settings.get('REQUEST_TIMEOUT', 10)
        self.default_country = geo_settings.get('DEFAULT_COUNTRY', 'Algeria')
        self.default_language = geo_settings.get('DEFAULT_LANGUAGE', 'fr,en')
        self.cache_enabled = geo_settings.get('CACHE_ENABLED', True)
        self.cache_timeout = geo_settings.get('CACHE_TIMEOUT', 3600)
        
        self.headers = {
            'User-Agent': self.user_agent
        }
    
    def _get_cache_key(self, operation, **params):
        """Génère une clé de cache pour les requêtes"""
        if not self.cache_enabled:
            return None
        
        key_parts = [operation] + [f"{k}:{v}" for k, v in sorted(params.items())]
        return f"geocoding:{'_'.join(key_parts)}"
    
    def geocode_address(self, address, country=None):
        """
        Convertit une adresse en coordonnées latitude/longitude
        """
        country = country or self.default_country
        cache_key = self._get_cache_key('geocode', address=address, country=country)
        
        # Vérifier le cache
        if cache_key:
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        
        try:
            # Attendre entre les requêtes (politique Nominatim)
            time.sleep(self.delay)
            
            params = {
                'q': f"{address}, {country}",
                'format': 'json',
                'limit': 1,
                'addressdetails': 1,
                'accept-language': self.default_language
            }
            
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise ValidationError(f"Erreur du service de géocodage: {response.status_code}")
            
            results = response.json()
            
            if not results:
                raise ValidationError(f"Adresse '{address}' non trouvée")
            
            result = results[0]
            
            geocoded_result = {
                'formatted_address': result.get('display_name', address),
                'latitude': float(result['lat']),
                'longitude': float(result['lon']),
                'verified': True,
                'place_id': result.get('place_id'),
                'address_components': result.get('address', {})
            }
            
            # Mettre en cache
            if cache_key:
                cache.set(cache_key, geocoded_result, self.cache_timeout)
            
            return geocoded_result
            
        except requests.RequestException as e:
            raise ValidationError(f"Erreur de connexion au service de géocodage: {str(e)}")
        except (KeyError, ValueError) as e:
            raise ValidationError(f"Erreur lors du traitement de la réponse: {str(e)}")
    
    def reverse_geocode(self, latitude, longitude):
        """
        Convertit des coordonnées en adresse
        """
        cache_key = self._get_cache_key('reverse', lat=latitude, lon=longitude)
        
        # Vérifier le cache
        if cache_key:
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        
        try:
            time.sleep(self.delay)
            
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'addressdetails': 1,
                'accept-language': self.default_language
            }
            
            response = requests.get(
                f"{self.base_url}/reverse",
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise ValidationError(f"Erreur du service de géocodage inverse: {response.status_code}")
            
            result = response.json()
            
            if 'error' in result:
                raise ValidationError(f"Coordonnées invalides: {result['error']}")
            
            reverse_result = {
                'formatted_address': result.get('display_name', f"{latitude}, {longitude}"),
                'latitude': latitude,
                'longitude': longitude,
                'verified': True,
                'address_components': result.get('address', {})
            }
            
            # Mettre en cache
            if cache_key:
                cache.set(cache_key, reverse_result, self.cache_timeout)
            
            return reverse_result
            
        except requests.RequestException as e:
            raise ValidationError(f"Erreur de connexion au service de géocodage: {str(e)}")
        except (KeyError, ValueError) as e:
            raise ValidationError(f"Erreur lors du traitement de la réponse: {str(e)}")
    
    def validate_coordinates(self, latitude, longitude, address=None):
        """
        Valide des coordonnées et optionnellement vérifie la proximité avec une adresse
        """
        geo_settings = getattr(settings, 'GEOLOCATION_SETTINGS', {})
        max_distance = geo_settings.get('MAX_VALIDATION_DISTANCE', 5000)
        
        # Validation basique des coordonnées
        if not (-90 <= latitude <= 90):
            raise ValidationError("Latitude invalide (doit être entre -90 et 90)")
        if not (-180 <= longitude <= 180):
            raise ValidationError("Longitude invalide (doit être entre -180 et 180)")
        
        # Si une adresse est fournie, vérifier la proximité
        if address:
            geocoded = self.geocode_address(address)
            distance = self._calculate_distance(
                latitude, longitude,
                geocoded['latitude'], geocoded['longitude']
            )
            
            # Si la distance est trop grande, alerter
            if distance > max_distance:
                raise ValidationError(
                    f"Les coordonnées ({latitude}, {longitude}) sont trop éloignées "
                    f"de l'adresse '{address}' (distance: {distance/1000:.2f}km)"
                )
        
        return {
            'latitude': latitude,
            'longitude': longitude,
            'verified': True
        }
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calcule la distance entre deux points en mètres (formule de Haversine)
        """
        R = 6371000  # Rayon de la Terre en mètres
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_phi / 2) * math.sin(delta_phi / 2) +
             math.cos(phi1) * math.cos(phi2) *
             math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c


class GeolocationService:
    """
    Service principal de géolocalisation
    """
    
    def __init__(self):
        self.geocoder = NominatimGeocoder()
    
    def process_location(self, nom_lieu, latitude=None, longitude=None):
        """
        Traite une localisation : adresse ou coordonnées
        """
        if latitude is not None and longitude is not None:
            # Coordonnées fournies : valider et obtenir l'adresse
            validated = self.geocoder.validate_coordinates(latitude, longitude, nom_lieu)
            try:
                reverse_result = self.geocoder.reverse_geocode(latitude, longitude)
                return {
                    'nom_lieu': nom_lieu or reverse_result['formatted_address'],
                    'latitude': latitude,
                    'longitude': longitude,
                    'formatted_address': reverse_result['formatted_address'],
                    'verified': True
                }
            except ValidationError:
                # Si le géocodage inverse échoue, utiliser les coordonnées
                return {
                    'nom_lieu': nom_lieu,
                    'latitude': latitude,
                    'longitude': longitude,
                    'formatted_address': nom_lieu,
                    'verified': False
                }
        else:
            # Seulement le nom : géocoder pour obtenir les coordonnées
            geocoded = self.geocoder.geocode_address(nom_lieu)
            return {
                'nom_lieu': nom_lieu,
                'latitude': geocoded['latitude'],
                'longitude': geocoded['longitude'],
                'formatted_address': geocoded['formatted_address'],
                'verified': True
            }
    
    def search_places(self, query, limit=None):
        """
        Recherche de lieux par nom
        """
        geo_settings = getattr(settings, 'GEOLOCATION_SETTINGS', {})
        limit = limit or geo_settings.get('DEFAULT_SEARCH_LIMIT', 5)
        
        cache_key = self.geocoder._get_cache_key('search', query=query, limit=limit)
        
        # Vérifier le cache
        if cache_key:
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        
        try:
            time.sleep(self.geocoder.delay)
            
            params = {
                'q': query,
                'format': 'json',
                'limit': limit,
                'addressdetails': 1,
                'accept-language': self.geocoder.default_language
            }
            
            response = requests.get(
                f"{self.geocoder.base_url}/search",
                params=params,
                headers=self.geocoder.headers,
                timeout=self.geocoder.timeout
            )
            
            if response.status_code != 200:
                return []
            
            results = response.json()
            
            search_results = [{
                'nom_lieu': result.get('display_name', ''),
                'latitude': float(result['lat']),
                'longitude': float(result['lon']),
                'type': result.get('type', ''),
                'importance': result.get('importance', 0)
            } for result in results]
            
            # Mettre en cache
            if cache_key:
                cache.set(cache_key, search_results, self.geocoder.cache_timeout)
            
            return search_results
            
        except Exception:
            return []
