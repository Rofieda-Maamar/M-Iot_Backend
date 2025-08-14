from rest_framework import serializers 
from .models import TypeParametre , CaptureSite , TypeParametre , TagRfid



class CaptureSiteSerializer(serializers.ModelSerializer) : 
    class Meta : 
        model = CaptureSite
        fields = [  'num_serie' , 'date_install' , 'date_dernier_serveillance'] 
    def create(self, validated_data):
        site = self.context.get('site')
        return CaptureSite.objects.create(site=site, **validated_data)


class TypeParametreSerializer (serializers.ModelSerializer) :
    capture = CaptureSiteSerializer()
    class Meta : 
        model = TypeParametre 
        fields = [ 'capture' , 'nom' , 'unite' , 'valeur_max']

    def create(self, validated_data):
        site = self.context.get('site')
        capture_data = validated_data.pop('capture')
        # Create or get capture with the site
        capture_serializer = CaptureSiteSerializer(data=capture_data, context={'site': site})
        capture_serializer.is_valid(raise_exception=True)
        capture = capture_serializer.save()

        return TypeParametre.objects.create(site=site, capture=capture, **validated_data)
    



class TagRfidSerializer(serializers.ModelSerializer) :
    class Meta : 
        model = TagRfid
        fields = ['site' ,'num_serie' , 'type' ,'date_install']