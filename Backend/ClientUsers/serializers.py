from rest_framework import serializers
from .models import ClientUser
from users.models import User


class ClientUserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    telephone = serializers.CharField(write_only=True)
    role = serializers.CharField(write_only=True)

    class Meta : 
        model = ClientUser
        fields = ['email', 'password', 'telephone', 'role']

    def validate_email (self , value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def create(self, validated_data):
        
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
