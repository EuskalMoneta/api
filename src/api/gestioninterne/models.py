from django.db import models


class Echeance(models.Model):

    """
    Référence échéance : à utiliser comme clé unique
    Nom ou Raison Sociale
    Prénom ou SIREN
    Numéro du débiteur
    Montant de échéance en Euro
    Date échéance
    Date opération
    """

    ref = models.CharField(max_length=50, unique=True)
    adherent_name = models.CharField(max_length=250)
    adherent_id = models.CharField(max_length=10)
    montant = models.DecimalField(max_digits=6, decimal_places=2)
    date = models.DateField()
    operation_date = models.DateField()
    cyclos_payment_id = models.CharField(max_length=50, blank=True)
    cyclos_error = models.CharField(max_length=500, blank=True)
