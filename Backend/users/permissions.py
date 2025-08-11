from rest_framework import permissions
from users.models import Admin , User
class IsAdminUser(permissions.BasePermission):
   

    def has_permission(self, request, view):
        user = request.user

        if not (
            user and
            user.is_authenticated and
            user.is_active and
            user.role == 'admin'
        ):
            return False

        try:
            admin = Admin.objects.get(user=user)
            return (
                admin.status == 'active'
            )
        except Admin.DoesNotExist:
            return False
        

        
class IsAjoutdescomptes(permissions.BasePermission):
    """
    Permission pour les utilisateurs dont :
    - user.role == 'admin'
    - et admin.role contient 'ajout des comptes'
    """

    def has_permission(self, request, view):
        user = request.user

        if not (user and user.is_authenticated and user.role == 'admin'):
            return False

        try:
            admin = Admin.objects.get(user=user)
            return  admin.status == 'active' and'ajout des comptes' in admin.role.split(',')
        except Admin.DoesNotExist:
            return False