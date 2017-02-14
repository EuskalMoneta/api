from django.db import models


class Beneficiaire(models.Model):

    owner = models.CharField(max_length=150)
    cyclos_id = models.CharField(max_length=30)
    cyclos_name = models.CharField(max_length=150)
    cyclos_account_number = models.CharField(max_length=30)

    class Meta:
        db_table = 'beneficiaire'
