from rest_framework import serializers 
from .models import TypeParametre , CaptureSite , TypeParametre , TagRfid



class TypeParametreSerializer (serializers.ModelSerializer) :
    class Meta : 
        model = TypeParametre 
        fields = [ 'nom' , 'unite' , 'valeur_max']





class CaptureSiteSerializer(serializers.ModelSerializer) : 
    # parametres inside capture bcs multiple parametres can be measured by the same capture 
    parametres = TypeParametreSerializer(many = True)
    class Meta : 
        model = CaptureSite
        fields = ['num_serie' , 'date_install' ,  "parametres"] 

    def create(self, validated_data):
        parametre_data = validated_data.pop('parametres' , [])
        site = self.context.get('site')
        if site is None:
            raise serializers.ValidationError("site is required in context to create a capture")

        capture = CaptureSite.objects.create(site=site ,**validated_data)
        # creat paramtres related to the site and capture 
        for param in parametre_data : 
            TypeParametre.objects.create(capture=capture , site = site , **param)

        return capture







class TagRfidSerializer(serializers.ModelSerializer) :
    class Meta : 
        model = TagRfid
        fields = ['site' ,'num_serie' , 'type' ,'date_install']