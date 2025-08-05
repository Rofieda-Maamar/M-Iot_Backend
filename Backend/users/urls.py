from django.urls import path
from .views import AddUserView , verify_email
from rest_framework_simplejwt.views import (
    TokenObtainPairView, 
    TokenRefreshView,
)



urlpatterns = [ 
    path('addUser/' ,AddUserView.as_view() , name='add-user' ) ,
    path('token/', TokenObtainPairView.as_view() , name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view() , name='token_refresh'),
    path('verify-email/<uidb64>/<token>/', verify_email, name='verify-email'),
]