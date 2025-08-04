# tickets/models.py
from django.db import models
from users.models import Admin 
from ClientUsers.models import ClientUser


class Ticket(models.Model):
    client_user = models.ForeignKey('ClientUsers.ClientUser', on_delete=models.CASCADE)
    type = models.CharField(max_length=50)
    urgence = models.CharField(max_length=20)
    objet = models.CharField(max_length=200)
    message = models.TextField()
    status_choices = [ 
        ('open','open'),
        ('resolved','resolved')
    ]
    status = models.CharField(max_length=20)

class ResponseTicket(models.Model):
    sender = models.ForeignKey('users.Admin', on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    message = models.TextField()

class FichierTicketReponse(models.Model):
    response_ticket = models.ForeignKey(ResponseTicket, on_delete=models.CASCADE)
    url = models.CharField(max_length=255)

class FichierTicket(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    url = models.CharField(max_length=255)
