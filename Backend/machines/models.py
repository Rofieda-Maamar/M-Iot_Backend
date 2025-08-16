from django.db import models

class Machine(models.Model):
    status_choices = [ 
        ('active','active'),
        ('inactive','inactive')
    ]
    site              = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='machines')
    identificateur    = models.CharField(max_length=100, unique=True)
    status              = models.CharField(max_length=20 ,choices=status_choices, default='active')
    #date_installation = models.DateTimeField()
    date_dernier_serv = models.DateTimeField(null=True, blank=True)

class CaptureMachine(models.Model):
    status_choices = [ 
        ('active','active'),
        ('inactive','inactive')
    ]
    machine           = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='captures')
    num_serie         = models.CharField(max_length=100, unique=True)
    status            = models.CharField(max_length=20 , choices=status_choices, default='active')
    date_install      = models.DateField()
    date_dernier_serveillance = models.DateField(null=True, blank=True)

# changes here 
class Parametre(models.Model) : 
    nom_choices =[
        ('temperateur','temperateur'),
        ('luminosite','luminosite') , 
        ('humidite','humidite') , 
        ('vibration','vibration') , 
        ('voltage','voltage') , 
        ('pression','pression') , 
        ('amperage' , 'amperage')
    ]
    captureMachine = models.ForeignKey(CaptureMachine , on_delete=models.CASCADE , related_name='parametre')  
    nom        = models.CharField(max_length=50)
    unite      = models.CharField(max_length=20)
    valeur_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

class MachineParametre(models.Model):
    parametre         = models.ForeignKey(Parametre, on_delete=models.CASCADE)
    valeur            = models.FloatField()
    date_heure        = models.DateTimeField()