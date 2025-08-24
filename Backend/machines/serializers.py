from rest_framework import serializers
from machines.models import CaptureMachine

from rest_framework import serializers
from machines.models import CaptureMachine
from rest_framework import serializers 
from .models import CaptureMachine  , Machine , Parametre
from django_tenants.utils import schema_context
from .models import *

from rest_framework.exceptions import ValidationError

class ParametreAddSerializer(serializers.ModelSerializer) : 
    class Meta : 
        model = Parametre
        fields = ['nom', 'unite' , 'valeur_max']


class CaptureMachineAddSerializer(serializers.ModelSerializer) : 
    parametre = ParametreAddSerializer(many=True, write_only=True)
    parametres = ParametreAddSerializer(many=True, source="parametre", read_only=True)
    class Meta : 
        model = CaptureMachine 
        fields = ['num_serie' , 'date_install' , 'parametre', 'parametres']
        
    def create(self, validated_data):
        parametres_data = validated_data.pop('parametre', [])
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



class DisplayMachinesDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        exclude = ["site"] 




class MachineDashboardSerializer(serializers.ModelSerializer) : 
    position = serializers.SerializerMethodField()
    class Meta :
        model = Machine 
        fields = ['status' , 'identificateur' , 'date_dernier_serv','position']

    def get_position(self , obj) : 
        if obj.site.latitude is not None and obj.site.longitude  is not None : 
            return {"latitude":obj.site.latitude , "longtitude" :obj.site.longitude}
        return None 
    


class CaptureLastValuesSerializer(serializers.ModelSerializer) :
    temp   = serializers.SerializerMethodField()
    humidite   = serializers.SerializerMethodField()
    luminosite = serializers.SerializerMethodField()
    vibration  = serializers.SerializerMethodField()
    voltage    = serializers.SerializerMethodField()
    pression   = serializers.SerializerMethodField()
    amperage   = serializers.SerializerMethodField()
    class Meta : 
        model = CaptureMachine
        fields = ['num_serie' ,'date_dernier_serveillance' , 'temp' ,
                 'humidite' , 'luminosite' , 'vibration' , 'voltage' ,'pression' , 'amperage']
        

    # to get the latest recorded value for a specific parameter param_name for a given capture
    def get_last_param_value(self, capture, param_name):
        last_value = MachineParametre.objects.filter(
            parametre__captureMachine=capture,
            parametre__nom=param_name
        ).order_by('-date_heure').first() # picks the most recent recorde
        return last_value.valeur if last_value else '-' #  return - if no values for that parametre (it means this capture don't capt his param)
     
    def get_temp(self, obj): # here obj is the CaptureMachine instance being serialized.
        return self.get_last_param_value(obj, 'temperateur')
    
    def get_humidite(self, obj):
        return self.get_last_param_value(obj, 'humidite')

    def get_luminosite(self, obj):
        return self.get_last_param_value(obj, 'luminosite')

    def get_vibration(self, obj):
        return self.get_last_param_value(obj, 'vibration')

    def get_voltage(self, obj):
        return self.get_last_param_value(obj, 'voltage')

    def get_pression(self, obj):
        return self.get_last_param_value(obj, 'pression')

    def get_amperage(self, obj):
        return self.get_last_param_value(obj, 'amperage')

