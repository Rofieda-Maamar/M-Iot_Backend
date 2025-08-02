# captures/models.py
from django.db import models

class CaptureSite(models.Model):
    site                   = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='captures')
    num_serie              = models.CharField(max_length=100, unique=True)
    status                 = models.CharField(max_length=20)
    date_install           = models.DateField()
    date_dernier_serveillance = models.DateField()



class CaptureRFID(models.Model):
    site                   = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='rfid_captures')
    num_serie              = models.CharField(max_length=100)
    status                 = models.CharField(max_length=20)
    date_install           = models.DateField()
    date_dernier_serveillance = models.DateField()



class ObjectTracking(models.Model):
    site            = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='object_trackings')
    capture_rfid    = models.ForeignKey(CaptureRFID, on_delete=models.CASCADE, related_name='object_trackings')
    categorie       = models.CharField(max_length=50)
    dernier_update  = models.DateTimeField()
    etat            = models.CharField(max_length=20)
    latitude_depart = models.FloatField(blank=True, null=True)
    longitude_depart= models.FloatField(blank=True, null=True)
    latitude_actuel = models.FloatField(blank=True, null=True)
    longitude_actuel= models.FloatField(blank=True, null=True)
    latitude_dest   = models.FloatField(blank=True, null=True)
    longitude_dest  = models.FloatField(blank=True, null=True)


class MesureTracking(models.Model):
    object_tracking  = models.ForeignKey(ObjectTracking, on_delete=models.CASCADE, related_name='mesures')
    date_passage     = models.DateField()
    lieu             = models.CharField(max_length=255)
    heure            = models.TimeField()
    duree_passage    = models.DurationField()

 



class TypeParametre(models.Model):
    nom        = models.CharField(max_length=50)
    unite      = models.CharField(max_length=20)
    valeur_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)



class SiteParametre(models.Model):
    capture    = models.ForeignKey(CaptureSite, on_delete=models.CASCADE, related_name='parametres')
    parametre  = models.ForeignKey(TypeParametre, on_delete=models.CASCADE)
    valeur     = models.FloatField()
    date_heure = models.DateTimeField()

   