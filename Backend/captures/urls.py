from django.urls import path
from .views import *

urlpatterns = [

    path('add-tag-rfid/', CreateTagRfidView.as_view(), name='add-tag-rfid'),
    path('upload-tag-rfid/', UploadTagRfidUserView.as_view(), name='upload-tag-rfid'),
    path('sse/realtime-parametre/', sse_realtime_parametre, name='sse_realtime_parametre'),
]
