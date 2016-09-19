from rest_framework import serializers


class IOStockBDCSerializer(serializers.Serializer):

    amount = serializers.CharField()
    porteur = serializers.CharField()
    description = serializers.CharField()


class ChangeEuroEuskoSerializer(serializers.Serializer):

    amount = serializers.CharField()
    payment_mode = serializers.CharField()
    member_login = serializers.CharField()


class ReconversionSerializer(serializers.Serializer):

    amount = serializers.CharField()
    facture = serializers.CharField()
    member_login = serializers.CharField()


class AccountsHistorySerializer(serializers.Serializer):

    account_type = serializers.CharField()


class BankDepositSerializer(serializers.Serializer):

    amount_minus_difference = serializers.BooleanField()
    amount_plus_difference = serializers.BooleanField()
    bordereau = serializers.CharField()
    deposit_amount = serializers.CharField(allow_blank=True)
    deposit_bank = serializers.CharField()
    deposit_calculated_amount = serializers.CharField()
    disable_bordereau = serializers.BooleanField()
    login_bdc = serializers.CharField()
    payment_mode = serializers.CharField()
    selected_payments = serializers.ListField()


class CashDepositSerializer(serializers.Serializer):
    deposit_amount = serializers.CharField()
    login_bdc = serializers.CharField()
    selected_payments = serializers.ListField()
