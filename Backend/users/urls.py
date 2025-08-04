from django.urls import path
from .views import AddUserView

urlpatterns = [ 
    path('addUser/' ,AddUserView.as_view() , name='add-user' ) ,
]