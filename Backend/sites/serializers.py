from .models import Site
from rest_framework import serializers
from captures.serializers import TypeParametreSerializer , CaptureSiteSerializer 
from captures.models import TypeParametre , CaptureSite 
from django_tenants.utils import schema_context

from rest_framework.exceptions import ValidationError

# for the client sites display
class SiteNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ['id','nom']


class SiteSerializer(serializers.ModelSerializer) : 
    captures = CaptureSiteSerializer(many = True)
    

    class Meta: 
        model= Site
        fields =['nom' , 'adresse' , 'latitude' , 'longitude' ,'asset_tracking', 'captures' ]

    def create(self , validated_data) : 
        # remove the captures from the data
        captures_data = validated_data.pop('captures' , []) # remove the capture to add the site object 
        schema_name = self.context.get('schema_name')
        if not schema_name:
            raise ValidationError("schema_name is required in serializer context to create site in tenant schema.")
        
        with schema_context(schema_name):
            # Create the site in that tenant's schema
            site = Site.objects.create(**validated_data)
        

            for capture_data in captures_data : 
                capture_serializer = CaptureSiteSerializer(data = capture_data , context={'site' : site}) # Pass the site object here ,
                #bcs the site isn't inside each capture , so pass the created site object to the capture , bcs it include in each capture the site as fk 
                capture_serializer.is_valid(raise_exception=True)
                capture_serializer.save()
            return site


class SiteDisplaySerializer(serializers.ModelSerializer): 
    parametre =serializers.SerializerMethodField()

    class Meta: 
        model = Site 
        fields = ['id','nom', 'adresse', 'date_ajout', 'parametre']

    def get_parametre(self, obj):
        # Get all parametre names for this site
        param_names = obj.parametre.values_list('nom', flat=True)
        return list(param_names)
    

class SiteUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Site
        fields = ['adresse']


class SiteCapturesDisplaySerializer (serializers.ModelSerializer) : 
    captures = CaptureSiteSerializer(many=True)

    class Meta : 
        model = Site
        fields = ['captures']