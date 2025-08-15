from django.urls import path , include
from .views import AddUserView , verify_email , ChangePasswordView , LoginView
from rest_framework_simplejwt.views import (
    TokenObtainPairView, 
    TokenRefreshView,
)

urlpatterns = [ 
    path('addUser/' ,AddUserView.as_view() , name='add-user' ) ,
    path('token/', LoginView.as_view() , name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view() , name='token_refresh'),
    path('verify-email/<uidb64>/<token>/', verify_email, name='verify-email'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('password-reset/', include('django_rest_passwordreset.urls', namespace='password-reset')),
]