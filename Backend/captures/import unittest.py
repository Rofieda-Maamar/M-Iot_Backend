import unittest
from unittest.mock import patch, Mock
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, date, time, timedelta
from rest_framework.test import APIRequestFactory
from rest_framework import status
import json
import pytz
from ..views import UpdatePositionRealTimeView
from ..models import TagRfid, MesseurTracking, ObjectTracking, PathTemplate, PositionHistorique
from sites.models import Site

class TestUpdatePositionRealTimeView(TestCase):
    """
    Tests for UpdatePositionRealTimeView
    """
    
    def setUp(self):
        """Set up test data"""
        self.factory = APIRequestFactory()
        self.view = UpdatePositionRealTimeView()
        
        # Create test site
        self.site = Site.objects.create(
            name="Test Site",
            address="Test Address"
        )
        
        # Create test tag RFID
        self.tag_rfid = TagRfid.objects.create(
            num_serie="TEST001",
            date_install=date.today(),
            type="actif",
            site=self.site
        )
        
        # Create test object tracking
        self.object_tracking = ObjectTracking.objects.create(
            categorie="Container",
            etat="stocke",
            capture_RFID=self.tag_rfid,
            site=self.site
        )
        
        # Create test path template
        self.path_template = PathTemplate.objects.create(
            nom="Test Route",
            source="Tlemcen Port",
            destination="Béjaïa Port",
            latitude_src=34.8833,
            longitude_src=-1.3167,
            latitude_dest=36.7500,
            longitude_dest=5.0833
        )
        
        # Create test messeur tracking
        self.messeur_tracking = MesseurTracking.objects.create(
            capture_rfid=self.tag_rfid,
            object_tracking=self.object_tracking,
            path=self.path_template,
            lieu="Tlemcen Port",
            date_debut=date.today(),
            date_fin=date.today() + timedelta(days=2),
            date_prevu=date.today(),
            heure=time(10, 0, 0),
            duree_passage="00:00:00"
        )
        
        # Test data for requests
        self.valid_data = {
            'tag_rfid_num_serie': 'TEST001',
            'latitude': 34.8900,
            'longitude': -1.3200,
            'timestamp': '2024-01-15T10:30:00Z'
        }
        
        self.invalid_data = {
            'tag_rfid_num_serie': 'INVALID',
            'latitude': None,
            'longitude': None
        }

    def test_post_valid_position_update(self):
        """Test successful position update with valid data"""
        request = self.factory.post('/api/captures/update-position-realtime/', self.valid_data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='Tlemcen, Algérie'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('Position mise à jour pour TEST001', response.data['message'])
        self.assertEqual(response.data['trajet_id'], self.path_template.id)

    def test_post_missing_required_fields(self):
        """Test POST with missing required fields"""
        incomplete_data = {
            'tag_rfid_num_serie': 'TEST001',
            'latitude': 34.8900
            # Missing longitude
        }
        
        request = self.factory.post('/api/captures/update-position-realtime/', incomplete_data)
        response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('requis', response.data['error'])

    def test_post_tag_not_found(self):
        """Test POST with non-existent tag"""
        data = self.valid_data.copy()
        data['tag_rfid_num_serie'] = 'NONEXISTENT'
        
        request = self.factory.post('/api/captures/update-position-realtime/', data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='Test Location'):
            response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('non trouvé', response.data['error'])

    def test_post_no_active_tracking(self):
        """Test POST when no active MesseurTracking exists"""
        # Delete the tracking
        self.messeur_tracking.delete()
        
        request = self.factory.post('/api/captures/update-position-realtime/', self.valid_data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='Test Location'):
            response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Aucun trajet actif', response.data['error'])

    def test_post_state_transition_to_transit(self):
        """Test object state transitions to en_transit"""
        # Position between source and destination
        data = {
            'tag_rfid_num_serie': 'TEST001',
            'latitude': 35.5000,  # Midway
            'longitude': 1.0000,
            'timestamp': '2024-01-15T12:00:00Z'
        }
        
        request = self.factory.post('/api/captures/update-position-realtime/', data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='En route'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.object_tracking.refresh_from_db()
        self.assertEqual(self.object_tracking.etat, 'en_transit')

    def test_post_state_transition_to_received(self):
        """Test object state transitions to reçu at destination"""
        # Position at destination
        data = {
            'tag_rfid_num_serie': 'TEST001',
            'latitude': 36.7500,  # Destination coordinates
            'longitude': 5.0833,
            'timestamp': '2024-01-15T15:00:00Z'
        }
        
        request = self.factory.post('/api/captures/update-position-realtime/', data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='Béjaïa Port'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.object_tracking.refresh_from_db()
        self.assertEqual(self.object_tracking.etat, 'reçu')

    def test_post_timestamp_parsing_with_z_suffix(self):
        """Test timestamp parsing with Z suffix"""
        data = self.valid_data.copy()
        data['timestamp'] = '2024-01-15T14:30:00Z'
        
        request = self.factory.post('/api/captures/update-position-realtime/', data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='Test Location'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that MesseurTracking was updated with correct time
        self.messeur_tracking.refresh_from_db()
        self.assertIsNotNone(self.messeur_tracking.date_prevu)
        self.assertIsNotNone(self.messeur_tracking.heure)

    def test_post_no_timestamp_uses_current_time(self):
        """Test that missing timestamp uses current time"""
        data = self.valid_data.copy()
        del data['timestamp']
        
        request = self.factory.post('/api/captures/update-position-realtime/', data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='Test Location'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that current date/time was used
        self.messeur_tracking.refresh_from_db()
        self.assertEqual(self.messeur_tracking.date_prevu, date.today())

    def test_post_creates_position_history(self):
        """Test that position updates create PositionHistorique entries"""
        request = self.factory.post('/api/captures/update-position-realtime/', self.valid_data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='New Location'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that PositionHistorique was created
        position_history = PositionHistorique.objects.filter(messeur_tracking=self.messeur_tracking)
        self.assertTrue(position_history.exists())
        
        latest_position = position_history.order_by('-timestamp').first()
        self.assertEqual(latest_position.latitude, float(self.valid_data['latitude']))
        self.assertEqual(latest_position.longitude, float(self.valid_data['longitude']))

    def test_get_current_coordinates_from_messeur(self):
        """Test getting coordinates from MesseurTracking fields"""
        # Add coordinates to messeur
        self.messeur_tracking.latitude = 34.8833
        self.messeur_tracking.longitude = -1.3167
        self.messeur_tracking.save()
        
        lat, lng = self.view.get_current_coordinates(self.messeur_tracking)
        
        self.assertEqual(lat, 34.8833)
        self.assertEqual(lng, -1.3167)

    def test_get_current_coordinates_from_history(self):
        """Test getting coordinates from PositionHistorique when not in MesseurTracking"""
        # Create position history
        PositionHistorique.objects.create(
            messeur_tracking=self.messeur_tracking,
            lieu="Test Location",
            latitude=35.0000,
            longitude=2.0000,
            timestamp=timezone.now()
        )
        
        lat, lng = self.view.get_current_coordinates(self.messeur_tracking)
        
        self.assertEqual(lat, 35.0000)
        self.assertEqual(lng, 2.0000)

    def test_get_current_coordinates_returns_none(self):
        """Test that get_current_coordinates returns None when no coordinates available"""
        lat, lng = self.view.get_current_coordinates(self.messeur_tracking)
        
        self.assertIsNone(lat)
        self.assertIsNone(lng)

    @patch('captures.views.GeolocationService')
    def test_get_location_from_coordinates_success(self, mock_service):
        """Test successful reverse geocoding"""
        mock_geocoder = Mock()
        mock_service.return_value.geocoder = mock_geocoder
        mock_geocoder.reverse_geocode.return_value = {
            'formatted_address': 'Tlemcen, Wilaya de Tlemcen, Algérie',
            'address_components': {
                'city': 'Tlemcen',
                'state': 'Wilaya de Tlemcen'
            }
        }
        
        result = self.view.get_location_from_coordinates(34.8833, -1.3167)
        
        self.assertEqual(result, 'Tlemcen, Wilaya de Tlemcen')

    def test_get_location_from_coordinates_invalid_input(self):
        """Test reverse geocoding with invalid coordinates"""
        result = self.view.get_location_from_coordinates(None, None)
        self.assertEqual(result, 'Position GPS inconnue')
        
        result = self.view.get_location_from_coordinates('', '')
        self.assertEqual(result, 'Position GPS inconnue')

    @patch('captures.views.GeolocationService')
    def test_get_location_from_coordinates_fallback(self, mock_service):
        """Test reverse geocoding fallback to GPS coordinates"""
        mock_service.side_effect = Exception("Geocoding failed")
        
        result = self.view.get_location_from_coordinates(34.8833, -1.3167)
        
        # Should return approximation based on _get_lieu_approximatif
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    @patch('django.core.cache.cache')
    def test_broadcast_sse_update(self, mock_cache):
        """Test SSE broadcast functionality"""
        test_data = {
            'type': 'position_update',
            'trajet_id': 1,
            'tag_rfid': 'TEST001'
        }
        
        self.view.broadcast_sse_update(test_data)
        
        # Verify cache.set was called with correct parameters
        self.assertEqual(mock_cache.set.call_count, 2)
        
        # Check the cache keys
        call_args_list = mock_cache.set.call_args_list
        cache_keys = [call[0][0] for call in call_args_list]
        
        self.assertIn('sse_update_1', cache_keys)
        self.assertIn('sse_update_all', cache_keys)

    def test_calculate_distance_function(self):
        """Test the distance calculation within the view"""
        data = {
            'tag_rfid_num_serie': 'TEST001',
            'latitude': 36.7500,  # Destination coordinates
            'longitude': 5.0833,
            'timestamp': '2024-01-15T15:00:00Z'
        }
        
        request = self.factory.post('/api/captures/update-position-realtime/', data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='Béjaïa Port'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check distances in response
        distances = response.data['distances']
        self.assertIn('source', distances)
        self.assertIn('destination', distances)
        self.assertIsInstance(distances['source'], (int, float))
        self.assertIsInstance(distances['destination'], (int, float))

    def test_duration_calculation_same_location(self):
        """Test duration calculation when object stays in same location"""
        # Create initial position history
        initial_time = timezone.now() - timedelta(hours=2)
        PositionHistorique.objects.create(
            messeur_tracking=self.messeur_tracking,
            lieu="Tlemcen Port",
            latitude=34.8833,
            longitude=-1.3167,
            timestamp=initial_time,
            date_entree=initial_time
        )
        
        # Update position at same location
        data = {
            'tag_rfid_num_serie': 'TEST001',
            'latitude': 34.8850,  # Slightly different but same location
            'longitude': -1.3170,
            'timestamp': timezone.now().isoformat()
        }
        
        request = self.factory.post('/api/captures/update-position-realtime/', data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='Tlemcen Port'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that duration was calculated
        self.messeur_tracking.refresh_from_db()
        self.assertNotEqual(self.messeur_tracking.duree_passage, "00:00:00")

    def test_duration_reset_on_location_change(self):
        """Test duration resets when object changes location"""
        data = {
            'tag_rfid_num_serie': 'TEST001',
            'latitude': 35.5000,  # Different location
            'longitude': 1.0000,
            'timestamp': timezone.now().isoformat()
        }
        
        request = self.factory.post('/api/captures/update-position-realtime/', data)
        
        with patch.object(self.view, 'get_location_from_coordinates', return_value='New Location'):
            with patch.object(self.view, 'broadcast_sse_update'):
                response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that duration was reset
        self.messeur_tracking.refresh_from_db()
        self.assertEqual(self.messeur_tracking.duree_passage, "00:00:00")

    def test_exception_handling(self):
        """Test general exception handling"""
        request = self.factory.post('/api/captures/update-position-realtime/', self.valid_data)
        
        with patch.object(self.view, 'get_location_from_coordinates', side_effect=Exception("Test error")):
            response = self.view.post(request)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('Erreur', response.data['error'])

    def test_database_lieu_approximation(self):
        """Test the _get_lieu_from_coordinates_database method"""
        # Test known location (Tlemcen)
        result = self.view._get_lieu_from_coordinates_database(34.88, -1.31)
        self.assertEqual(result, "Tlemcen, Algérie")
        
        # Test unknown location
        result = self.view._get_lieu_from_coordinates_database(40.0, 10.0)
        self.assertIsNone(result)

    def test_approximation_fallback(self):
        """Test the _get_lieu_approximatif method"""
        # Test Algeria coordinates
        result = self.view._get_lieu_approximatif(34.88, -1.31)
        self.assertIn("Algérie", result)
        
        # Test Morocco coordinates
        result = self.view._get_lieu_approximatif(33.0, -7.0)
        self.assertEqual(result, "Maroc")
        
        # Test Tunisia coordinates
        result = self.view._get_lieu_approximatif(33.9, 10.1)
        self.assertEqual(result, "Tunisie")
        
        # Test unknown coordinates
        result = self.view._get_lieu_approximatif(50.0, 50.0)
        self.assertIn("Position", result)

    def tearDown(self):
        """Clean up test data"""
        PositionHistorique.objects.all().delete()
        MesseurTracking.objects.all().delete()
        ObjectTracking.objects.all().delete()
        PathTemplate.objects.all().delete()
        TagRfid.objects.all().delete()
        Site.objects.all().delete()