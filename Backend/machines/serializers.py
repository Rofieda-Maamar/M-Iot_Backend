from rest_framework import serializers 
from .models import CaptureMachine  , Machine , Parametre
from django_tenants.utils import schema_context

from rest_framework.exceptions import ValidationError

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
        schema_name = self.context.get('schema_name')
        if not schema_name:
            raise ValidationError("schema_name is required in serializer context to create site in tenant schema.")

        with schema_context(schema_name):
            identificateur = validated_data.get('identificateur')
            if Machine.objects.filter(identificateur=identificateur).exists() :
                raise ValidationError({"identificateur" : f"machine with identificateur '{identificateur}' already exists"})
            machine = Machine.objects.create(**validated_data)       # creat the machine object

            for capture_data in captures_data:                       # for each capture in the captures list
                data_with_machine = {**capture_data, "machine": machine}
                
                capture_serializer = CaptureMachineAddSerializer(
                    data=data_with_machine,
                    context=self.context
                )
                capture_serializer.is_valid(raise_exception=True)
                capture_serializer.save(machine=machine)
            return machine
        



class DisplayMachinesSerializer(serializers.ModelSerializer) : 
    captures = CaptureMachineAddSerializer(many = True)
    class Meta : 
        model = Machine
        fields =['identificateur' , 'status' ,'date_dernier_serv' , 'captures']


class CaptureMachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaptureMachine
        fields = '__all__'