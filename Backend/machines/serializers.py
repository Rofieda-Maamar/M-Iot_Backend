from rest_framework import serializers 
from .models import CaptureMachine  , Machine , Parametre



class ParametreAddSerializer(serializers.ModelSerializer) : 
    class Meta : 
        model = Parametre
        fields = ['nom', 'unite' , 'valeur_max']


class CaptureMachineAddSerializer(serializers.ModelSerializer) : 
    parametre = ParametreAddSerializer(many =True)
    class Meta : 
        model = CaptureMachine 
        fields = ['num_serie' , 'date_install' , 'parametre']
        
    def create(self, validated_data):
        parametres_data = validated_data.pop('parametre',[])
        capture = CaptureMachine.objects.create(**validated_data)
        for param_data in parametres_data : 
            Parametre.objects.create(captureMachine = capture, **param_data)
        return capture



class MachineAddSerializer(serializers.ModelSerializer) : 
    captures = CaptureMachineAddSerializer(many = True)
    class Meta: 
        model = Machine 
        fields=['site' , 'identificateur', 'status'  , 'captures']    

    def create(self, validated_data):
        captures_data = validated_data.pop('captures' , [])           # remove the captures to add the machine object
        machine = Machine.objects.create(**validated_data)       # creat the machine object

        capture_serializer = CaptureMachineAddSerializer()

        for capture_data in captures_data:                       # for each capture in the captures list
            capture_serializer.create({**capture_data , "machine" :machine })
        return machine