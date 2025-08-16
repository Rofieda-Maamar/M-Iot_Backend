from rest_framework import serializers
from machines.models import CaptureMachine

class CaptureMachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaptureMachine
        fields = '__all__'
