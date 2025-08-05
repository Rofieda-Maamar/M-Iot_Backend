from django.urls import path , include
from .views import AddAdminView, AddUserView, AdminDeactivateAPIView, AdminDetailView, AdminListView, AdminSearchAPIView, AdminUpdateAPIView , verify_email , ChangePasswordView 
from rest_framework_simplejwt.views import (
    TokenObtainPairView, 
    TokenRefreshView,
)



urlpatterns = [ 
    path('addUser/' ,AddUserView.as_view() , name='add-user' ) ,
    path('token/', TokenObtainPairView.as_view() , name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view() , name='token_refresh'),
    path('verify-email/<uidb64>/<token>/', verify_email, name='verify-email'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('password-reset/', include('django_rest_passwordreset.urls', namespace='password-reset')),
    
    path('add-admin/', AddAdminView.as_view(), name='add-admin'),
    path('admins/', AdminListView.as_view(), name='admin-list'),
    path('admins/<int:id>/', AdminDetailView.as_view(), name='admin-detail'),
    path('admins/<int:id>/update/', AdminUpdateAPIView.as_view(), name='admin-update'),
    path('admins/<int:id>/deactivate/', AdminDeactivateAPIView.as_view(), name='admin-deactivate'),
    path('admins/search/', AdminSearchAPIView.as_view(), name='admin-search'),
]