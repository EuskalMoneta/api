from rest_framework import serializers


class EntreeStockBDCSerializer(serializers.Serializer):

    selected_payments = serializers.ListField()
    login_bdc = serializers.CharField()


class SortieStockBDCSerializer(serializers.Serializer):

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
    filter = serializers.CharField(required=False)
    direction = serializers.CharField(required=False)


class BankDepositSerializer(serializers.Serializer):

    bordereau = serializers.CharField(required=False)
    deposit_amount = serializers.CharField(allow_blank=True)
    deposit_bank = serializers.CharField()
    deposit_bank_name = serializers.CharField()
    deposit_calculated_amount = serializers.CharField()
    disable_bordereau = serializers.BooleanField()
    login_bdc = serializers.CharField()
    payment_mode = serializers.CharField()
    payment_mode_name = serializers.CharField()
    selected_payments = serializers.ListField()


class CashDepositSerializer(serializers.Serializer):
    deposit_amount = serializers.CharField()
    login_bdc = serializers.CharField()
    mode = serializers.CharField()
    selected_payments = serializers.ListField()


class DepotEuskoNumeriqueSerializer(serializers.Serializer):
    amount = serializers.CharField()
    login_bdc = serializers.CharField()
    member_login = serializers.CharField()


class RetraitEuskoNumeriqueSerializer(serializers.Serializer):
    amount = serializers.CharField()
    login_bdc = serializers.CharField()
    member_login = serializers.CharField()


class MemberAccountsSummariesSerializer(serializers.Serializer):
    member_login = serializers.CharField()


class PaymentsAvailableEntreeStock(serializers.Serializer):
    login_bdc = serializers.CharField()
