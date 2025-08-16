from django.urls import path , include
from .views import AddUserView , verify_email , ChangePasswordView , LoginView ,CookieTokenRefreshView


urlpatterns = [ 
    path('addUser/' ,AddUserView.as_view() , name='add-user' ) ,
    path('token/', LoginView.as_view() , name='token_obtain_pair'),
    path('token/refresh/', CookieTokenRefreshView.as_view() , name='token_refresh'),
    path('verify-email/<uidb64>/<token>/', verify_email, name='verify-email'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('password-reset/', include('django_rest_passwordreset.urls', namespace='password-reset')),
    
]