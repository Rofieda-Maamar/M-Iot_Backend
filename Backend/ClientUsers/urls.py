from django.urls import path
from .views import AddClientUserView ,UploadClientUserView

urlpatterns = [

    path('add-clientuser/', AddClientUserView.as_view(), name='add-Clientuser'),
    path('upload-clientuser/', UploadClientUserView.as_view(), name='add-Clientuser'),

]
