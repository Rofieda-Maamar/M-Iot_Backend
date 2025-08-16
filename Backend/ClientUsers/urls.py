from django.urls import path
from .views import AddClientUserView ,UploadClientUserView ,displayListUsersClientView

urlpatterns = [

    path('add-clientuser/', AddClientUserView.as_view(), name='add-Clientuser'),
    path('upload-clientuser/', UploadClientUserView.as_view(), name='add-Clientuser'),
    path('list-clientuser/', displayListUsersClientView.as_view(), name='list-Clientuser'),

]
