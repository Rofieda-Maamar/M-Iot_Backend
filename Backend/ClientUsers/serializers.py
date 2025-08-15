from rest_framework import serializers
from .models import ClientUser
from users.models import User
from rest_framework.exceptions import ValidationError
from django_tenants.utils import schema_context

class ClientUserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    telephone = serializers.CharField(write_only=True)
    role = serializers.CharField(write_only=True)

    class Meta : 
        model = ClientUser
        fields = ['email', 'password', 'telephone', 'role']

    def validate_email (self , value):
        # validate user with this email on the tennant users
        schema_name = self.context.get('schema_name')
        if not schema_name : 
            raise ValidationError("schema name is required ")
        with schema_context(schema_name) :
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def create(self, validated_data):
        schema_name = self.context.get('schema_name')
        if not schema_name : 
            raise ValidationError("schema name is required ")
        with schema_context(schema_name) : 
            email = validated_data.pop('email')
            password=validated_data.pop('password')
            telephone= validated_data.pop('telephone')
            user = User.objects.create(
                email=email,
                role ='userCllient',
                telephone= telephone
            )
            user.set_password(password)
            user.save()
            # creat the client user and link it to the created user
            client_user = ClientUser.objects.create(
                user_id=user.id ,
                **validated_data # the role 
            ) 
        
        return client_user
