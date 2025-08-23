from django.urls import path
<<<<<<< HEAD
from .views import (CreateTagRfidView, UploadTagRfidUserView, 
                   PlanifierTrajetView, TrackingPointListView, 
                   ObjectTrackingListView, PathTemplateListView, 
                   ObjectTrackingNamesView, GeocodeAddressView,
                   ReverseGeocodeView, SearchPlacesView, TrajetListView,
                   TrajetHistoriqueView, UpdatePositionRealTimeView,
                   trajet_sse_stream, trajet_stream_all ,CheckObjetStatusView)
=======
from .views import *
>>>>>>> Rofieda

urlpatterns = [
    path('add-tag-rfid/', CreateTagRfidView.as_view(), name='add-tag-rfid'),
    path('upload-tag-rfid/', UploadTagRfidUserView.as_view(), name='upload-tag-rfid'),
<<<<<<< HEAD
    
    # URLs pour la planification de trajet
    path('tracking-points/', TrackingPointListView.as_view(), name='tracking-points-list'),
    path('object-tracking/', ObjectTrackingListView.as_view(), name='object-tracking-list'),
    path('object-tracking-names/', ObjectTrackingNamesView.as_view(), name='object-tracking-names'),
    path('planifier-trajet/', PlanifierTrajetView.as_view(), name='planifier-trajet'),
    path('path-templates/', PathTemplateListView.as_view(), name='path-templates-list'),
    
    # URLs pour la liste et historique des trajets
    path('liste-trajets/', TrajetListView.as_view(), name='liste-trajets'),
    path('trajet-historique/<int:trajet_id>/', TrajetHistoriqueView.as_view(), name='trajet-historique'),
    path('update-position-realtime/', UpdatePositionRealTimeView.as_view(), name='update-position-realtime'),
    
    
    
    # URLs pour SSE (Server-Sent Events) - Temps réel
    path('trajet-stream/', trajet_sse_stream, name='trajet-stream'),
    path('trajet-stream/<int:trajet_id>/', trajet_sse_stream, name='trajet-stream-specific'),
    path('trajet-stream-all/', trajet_stream_all, name='trajet-stream-all'),
    
    # URL pour vérification du statut des objets
    path('check-objet-status/', CheckObjetStatusView.as_view(), name='check-objet-status'),
    
    # URLs pour la géolocalisation (Leaflet/OpenStreetMap)
    path('geocode/', GeocodeAddressView.as_view(), name='geocode-address'),
    path('reverse-geocode/', ReverseGeocodeView.as_view(), name='reverse-geocode'),
    path('search-places/', SearchPlacesView.as_view(), name='search-places'),
=======
    path('list-tag-rfid/', ListTagRfidView.as_view(), name='list-tag-rfid'),
    path('sse/realtime-parametre/', sse_realtime_parametre, name='sse_realtime_parametre'),
>>>>>>> Rofieda
]
