# captures/models.py
from django.db import models
from sites.models import Site

class CaptureSite(models.Model):
    STATUS_CHOICES = [
        ('active', 'active'),
        ('inactive', 'inactive'),
    ]
    site                   = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='captures')
    num_serie              = models.CharField(max_length=100, unique=True)
    status                 = models.CharField(max_length=20 , choices=STATUS_CHOICES , default='active')
    date_install           = models.DateField()
    date_dernier_serveillance = models.DateField()

class TagRfid(models.Model):
    STATUS_CHOICES = [
        ('active', 'active'),
        ('inactive', 'inactive'),
    ]
    Type_choices = [
        ('actif', 'Actif'),
        ('passif', 'Passif'),
    ]
    site                   = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='rfid_captures')
    num_serie = models.CharField(max_length=100, unique=True)
    status  = models.CharField(max_length=20,choices=STATUS_CHOICES , default='active' )
    type    = models.CharField(max_length=20, choices=Type_choices, default='actif')
    date_install           = models.DateField()
    date_dernier_serveillance = models.DateField(null=True, blank=True)

class ObjectTracking(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    capture_RFID = models.ForeignKey(TagRfid, on_delete=models.CASCADE)
    categorie = models.CharField(max_length=50)
    etat = models.CharField(max_length=20)

class TrackingPoint(models.Model):
    nom_lieu = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField() 

class PathTemplate(models.Model):
    nom = models.CharField(max_length=100)
    source = models.CharField(max_length=100) 
    destination = models.CharField(max_length=100)
    latitude_src = models.FloatField()
    longitude_src = models.FloatField()
    latitude_dest = models.FloatField()
    longitude_dest = models.FloatField()

class PathTemplatePoint(models.Model):
    template = models.ForeignKey(PathTemplate, on_delete=models.CASCADE)
    point = models.ForeignKey(TrackingPoint, on_delete=models.CASCADE)
    ordre = models.IntegerField()

class MesseurTracking(models.Model):
    capture_rfid = models.ForeignKey(TagRfid, on_delete=models.CASCADE)
    path = models.ForeignKey(PathTemplate, on_delete=models.CASCADE)
    object_tracking = models.ForeignKey(ObjectTracking, on_delete=models.CASCADE)
    date_debut = models.DateField()
    date_fin = models.DateField()
    date_prevu = models.DateField()
    lieu = models.CharField(max_length=255)
    heure = models.TimeField()
    duree_passage = models.TimeField()

    class Meta:
        unique_together = ('capture_rfid', 'path')



class TypeParametre(models.Model):
    nom_choices =[
        ('temperateur','temperateur'),
        ('luminosite','luminosite') , 
        ('humidite','humidite') , 
        ('vibration','vibration') , 
        ('voltage','voltage') , 
        ('pression','pression') , 
        ('amperage' , 'amperage')
    ]
    site = models.ForeignKey(Site , on_delete=models.CASCADE , related_name='parametre')  
    capture    = models.ForeignKey(CaptureSite, on_delete=models.CASCADE, related_name='parametres')
    nom        = models.CharField(max_length=50)
    unite      = models.CharField(max_length=20)
    valeur_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

class SiteParametre(models.Model):
    typeParametre = models.ForeignKey(TypeParametre , on_delete=models.CASCADE , related_name='valeurs')
    valeur     = models.FloatField()
    date_heure = models.DateTimeField()
