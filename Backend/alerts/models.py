from django.db import models

class AlerteRule(models.Model):
    status         = models.CharField(max_length=20)
    designation    = models.CharField(max_length=100)
    type           = models.CharField(max_length=50)
    capture_machine= models.ForeignKey('machines.CaptureMachine', on_delete=models.CASCADE, null=True, blank=True)
    intervalle_min = models.FloatField()
    intervalle_max = models.FloatField()
    date_debut     = models.DateField()
    date_fin       = models.DateField()
    heure_debut    = models.TimeField()
    heure_fin      = models.TimeField()
    frequence      = models.CharField(max_length=50)
    nb_notifs_jour = models.IntegerField()
    message        = models.TextField()
    via_sms        = models.BooleanField(default=False)
    via_email      = models.BooleanField(default=False)
    tel_notif      = models.CharField(max_length=20, blank=True, null=True)
    email_notif    = models.EmailField(blank=True, null=True)



class AlertLog(models.Model):
    capture_machine= models.ForeignKey('machines.CaptureMachine', on_delete=models.CASCADE, null=True, blank=True)
    nbr_email      = models.IntegerField(default=0)
    nbr_sms        = models.IntegerField(default=0)
    date_heure     = models.DateTimeField()