from django.contrib.auth import hashers
from django.db import models


class Beneficiaire(models.Model):

    owner = models.CharField(max_length=6)
    cyclos_id = models.CharField(max_length=30)
    cyclos_name = models.CharField(max_length=150)
    cyclos_account_number = models.CharField(max_length=30)

    class Meta:
        db_table = 'beneficiaire'
        unique_together = ('owner', 'cyclos_account_number')


class SecurityAnswer(models.Model):
    """
    Inspired by https://github.com/praetorianlabs-amarquez/django-security-questions.
    """

    owner = models.CharField(max_length=6, unique=True)
    question = models.ForeignKey('SecurityQuestion')
    answer = models.CharField(max_length=150, null=False, blank=False)

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


class SecurityQuestion(models.Model):

    question = models.CharField(max_length=150, null=False, blank=False)
    predefined = models.BooleanField(default=False)

    class Meta:
        db_table = 'security_question'
