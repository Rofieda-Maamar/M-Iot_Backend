from django.urls import reverse
from rest_framework import serializers
from .models import User , Admin
from django.db import transaction

class UserSerializer (serializers.ModelSerializer) :
    password = serializers.CharField(write_only=True)
    class Meta : 
        model = User
        fields = [ 'email' , 'password' , 'telephone' , 'role']

    def create(self, validated_data):
        password =validated_data.pop('password')
        user= User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    

class ChangePasswordSerializer(serializers.Serializer) :
    model=User
    old_password =serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class AdminSerializer(serializers.ModelSerializer):
    # User fields
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    telephone = serializers.CharField(write_only=True)

    # Admin fields
    nom = serializers.CharField()
    prenom = serializers.CharField()
    role = serializers.ListField(child=serializers.CharField(), write_only=True)  # <-- list of roles (checkboxes)

    class Meta:
        model = Admin
        fields = ['email', 'password', 'telephone', 'nom', 'prenom', 'role']

    def create(self, validated_data):
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        telephone = validated_data.pop('telephone')

        nom = validated_data.pop('nom')
        prenom = validated_data.pop('prenom')
        roles_list = validated_data.pop('role')  # list from checkboxes

        with transaction.atomic():
            # Create User with fixed role
            user = User.objects.create(
                email=email,
                telephone=telephone,
                role='admin'
            )
            user.set_password(password)
            user.save()

            # Create Admin with comma-separated roles
            admin = Admin.objects.create(
                user=user,
                nom=nom,
                prenom=prenom,
                role=",".join(roles_list),  # convert list to string
                status='active'
            )

        return admin
    

    
class AdminListSerializer(serializers.ModelSerializer):
    fullname = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email')
    telephone = serializers.CharField(source='user.telephone')
    detail = serializers.SerializerMethodField()

    class Meta:
        model = Admin
        fields = ['id', 'fullname', 'email', 'telephone', 'status', 'detail']

    def get_fullname(self, obj):
        return f"{obj.nom} {obj.prenom}"

    def get_detail(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f"/api/user/admins/{obj.id}/")
        return f"/api/user/admins/{obj.id}/"

class AdminDetailSerializer(serializers.ModelSerializer):
    fullname = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email')
    telephone = serializers.CharField(source='user.telephone')
    created_at = serializers.SerializerMethodField()

    update_url = serializers.SerializerMethodField()
    deactivate_url = serializers.SerializerMethodField()

    class Meta:
        model = Admin
        fields = ['id', 'fullname', 'email', 'telephone', 'role', 'created_at', 'update_url', 'deactivate_url']

    def get_created_at(self, obj):
        return obj.user.created_at.date().isoformat()
    
    def get_fullname(self, obj):
        return f"{obj.nom} {obj.prenom}"
    
  
    
    def get_update_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f"/api/user/admins/{obj.id}/update/")
        return f"/api/user/admins/{obj.id}/update/"
        

    def get_deactivate_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f"/api/user/admins/{obj.id}/deactivate/")
        return f"/api/user/admins/{obj.id}/deactivate/"

class AdminUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email')
    telephone = serializers.CharField(source='user.telephone')
    role = serializers.ListField(child=serializers.CharField())

    fullname = serializers.CharField(write_only=True)

    class Meta:
        model = Admin
        fields = ['fullname', 'role', 'email', 'telephone']

    def update(self, instance, validated_data):
        # Traiter fullname
        fullname = validated_data.pop('fullname', '')
        if fullname:
            parts = fullname.strip().split()
            instance.nom = parts[0]
            instance.prenom = ' '.join(parts[1:]) if len(parts) > 1 else ''

        # Traiter les rôles
        instance.role = ','.join(validated_data.get('role', instance.role.split(',')))
        instance.save()

        # Traiter l'utilisateur lié
        user_data = validated_data.get('user', {})
        user = instance.user
        user.email = user_data.get('email', user.email)
        user.telephone = user_data.get('telephone', user.telephone)
        user.save()

        return instance

class AdminDeactivateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = ['status']

    def update(self, instance, validated_data):
        instance.status = 'inactive'
        instance.save()
        return instance