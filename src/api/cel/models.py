from django.contrib.auth import hashers
from django.db import models
from simple_history.models import HistoricalRecords


class Beneficiaire(models.Model):

    owner = models.CharField(max_length=6)
    cyclos_id = models.CharField(max_length=30)
    cyclos_name = models.CharField(max_length=150)
    cyclos_account_number = models.CharField(max_length=30)

    class Meta:
        db_table = 'beneficiaire'
        unique_together = ('owner', 'cyclos_account_number')


class Mandat(models.Model):
    """
    Représente un mandat de prélèvement entre deux adhérents.

    Le débiteur autorise le créditeur à effectuer des prélèvements sur son compte, dont il lui a donné le numéro. Les
    deux parties prenantes sont identifiées par leur numéro de compte. Les noms du débiteur et du créditeur sont
    également enregistrés avec le mandat, pour diminuer le nombre de requêtes à faire par la suite auprès de Cyclos
    pour afficher les mandats.
    """
    numero_compte_debiteur = models.CharField(max_length=9)
    nom_debiteur = models.CharField(max_length=150)
    numero_compte_crediteur = models.CharField(max_length=9)
    nom_crediteur = models.CharField(max_length=150)
    EN_ATTENTE = 'ATT'
    VALIDE = 'VAL'
    REFUSE = 'REF'
    REVOQUE = 'REV'
    STATUTS = (
        (EN_ATTENTE, 'En attente de validation'),
        (VALIDE, 'Validé'),
        (REFUSE, 'Refusé'),
        (REVOQUE, 'Révoqué'),
    )
    statut = models.CharField(max_length=3, choices=STATUTS, default=EN_ATTENTE)
    history = HistoricalRecords()

    class Meta:
        db_table = 'mandat'
        unique_together = ('numero_compte_crediteur', 'numero_compte_debiteur')

    @property
    def date_derniere_modif(self):
        return self.history.latest().history_date.date()


class PredefinedSecurityQuestion(models.Model):

    question = models.CharField(max_length=150)
    LANGUAGES = [
        ('eu', 'eu'),
        ('fr', 'fr'),
    ]
    language = models.CharField(max_length=2, choices=LANGUAGES)

    class Meta:
        db_table = 'predefined_security_question'


class SecurityAnswer(models.Model):
    """
    Inspired by https://github.com/praetorianlabs-amarquez/django-security-questions.
    """

    owner = models.CharField(max_length=6, unique=True)
    question = models.CharField(max_length=150)
    answer = models.CharField(max_length=150)

    class Meta:
        db_table = 'security_answer'

    def hash_current_answer(self):
        self.set_answer(self.answer)

    def set_answer(self, raw_answer):
        raw_answer = raw_answer.lower()
        self.answer = hashers.make_password(raw_answer)

    def check_answer(self, raw_answer):
        raw_answer = raw_answer.lower()

        def setter(raw_answer):
            self.set_answer(raw_answer)
            self.save(update_fields=["answer"])
        return hashers.check_password(raw_answer, self.answer, setter)

    def set_unusable_answer(self):
        self.answer = hashers.make_password(None)

    def has_usable_answer(self):
        return hashers.is_password_usable(self.answer)
