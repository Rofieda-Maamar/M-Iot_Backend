from rest_framework import serializers
from .models import User

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