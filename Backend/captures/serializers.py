from rest_framework import serializers 
from .models import *
from rest_framework.exceptions import ValidationError
from django_tenants.utils import schema_context

class TypeParametreSerializer (serializers.ModelSerializer) :
    class Meta : 
        model = TypeParametre 
        fields = [ 'nom' , 'unite' , 'valeur_max']





class CaptureSiteSerializer(serializers.ModelSerializer) : 
    # parametres inside capture bcs multiple parametres can be measured by the same capture 
    parametres = TypeParametreSerializer(many = True)
    status = serializers.ReadOnlyField()
    class Meta : 
        model = CaptureSite
        fields = ['num_serie' , 'date_install' ,  "parametres" , 'status'] 

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



class ObjectTrackingSerializer(serializers.ModelSerializer):
    class Meta : 
        model=ObjectTracking 
        fields = '__all__'



class TagRfidSerializer(serializers.ModelSerializer) :
    ObjectTracking = ObjectTrackingSerializer(read_only=True)
    categorie = serializers.CharField(write_only=True)

    class Meta : 
        model = TagRfid
        fields = ['site' ,'num_serie' , 'type' ,'date_install' ,'ObjectTracking','categorie']

    def create(self, validated_data):
        categorie = validated_data.pop("categorie")
        tag_rfid = TagRfid.objects.create(**validated_data)

        ## creat the object traking linked to the tagrfid 
        ObjectTracking.objects.create(
            site=tag_rfid.site, 
            capture_RFID=tag_rfid, 
            categorie=categorie,
            etat= "stocké"
        )
        return tag_rfid






class RealtimeParametreSerializer(serializers.ModelSerializer):
    nom = serializers.CharField(source='typeParametre.nom')
    unite = serializers.CharField(source='typeParametre.unite')
    valeur_max = serializers.DecimalField(source='typeParametre.valeur_max', max_digits=10, decimal_places=2)

    class Meta:
        model = SiteParametre
        fields = ['nom', 'unite', 'valeur_max', 'valeur', 'date_heure']