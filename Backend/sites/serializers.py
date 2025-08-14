from .models import Site
from rest_framework import serializers
from captures.serializers import TypeParametreSerializer , CaptureSiteSerializer
from captures.models import TypeParametre , CaptureSite 



# for the client sites display
class SiteNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ['id','nom']


class SiteSerializer(serializers.ModelSerializer) : 
    parametre = TypeParametreSerializer(many = True)
    

    class Meta: 
        model= Site
        fields =['nom' , 'adresse' , 'latitude' , 'longitude' ,'asset_tracking', 'parametre' ]

    def create(self , validated_data) : 
        # remove the parametre from the request body
        parametred_data = validated_data.pop('parametre' , [])
       
        #creat the site object 
        site = Site.objects.create(**validated_data)
        # creat the parametres , and associate them to this site

        for param in parametred_data : 
            serializer = TypeParametreSerializer(data=param, context={'site': site})
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return site

