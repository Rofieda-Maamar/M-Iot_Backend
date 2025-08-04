from django.db import models

class Machine(models.Model):
    status_choices = [ 
        ('active','active'),
        ('inactive','inactive')
    ]
    site              = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='machines')
    identificateur    = models.CharField(max_length=100)
    status              = models.CharField(max_length=20 ,choices=status_choices, default='active')
    date_installation = models.DateTimeField()
    date_dernier_serv = models.DateTimeField()



class CaptureMachine(models.Model):
    status_choices = [ 
        ('active','active'),
        ('inactive','inactive')
    ]
    machine           = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='captures')
    num_serie         = models.CharField(max_length=100, unique=True)
    status            = models.CharField(max_length=20 , choices=status_choices, default='active')
    date_install      = models.DateField()
    date_dernier_serveillance = models.DateField()


class MachineParametre(models.Model):
    capture_machine   = models.ForeignKey(CaptureMachine, on_delete=models.CASCADE, related_name='parametres')
    parametre         = models.ForeignKey('captures.TypeParametre', on_delete=models.CASCADE)
    valeur            = models.FloatField()
    date_heure        = models.DateTimeField()

