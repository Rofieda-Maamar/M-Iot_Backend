# tickets/models.py
from django.db import models

class Ticket(models.Model):
    client_user  = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='tickets')
    type         = models.CharField(max_length=50)
    urgence      = models.CharField(max_length=20)
    objet        = models.CharField(max_length=200)
    message      = models.TextField()
    etat         = models.CharField(max_length=20)

class ResponseTicket(models.Model):
    ticket   = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='responses')
    sender   = models.ForeignKey('users.User', on_delete=models.CASCADE)
    message  = models.TextField()
    file     = models.FileField(upload_to='ticket_responses/', blank=True, null=True)

class TicketFile(models.Model):
    ticket  = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='files')
    url     = models.URLField()
