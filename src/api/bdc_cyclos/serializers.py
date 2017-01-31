from rest_framework import serializers


class EntreeStockBDCSerializer(serializers.Serializer):

    selected_payments = serializers.ListField()
    login_bdc = serializers.CharField()


class SortieStockBDCSerializer(serializers.Serializer):

    amount = serializers.CharField()
    porteur = serializers.CharField()
    description = serializers.CharField()
    login_bdc = serializers.CharField(required=False)


class ChangeEuroEuskoSerializer(serializers.Serializer):

    amount = serializers.CharField()
    payment_mode = serializers.CharField()
    payment_mode_name = serializers.CharField()
    member_login = serializers.CharField()


class ReconversionSerializer(serializers.Serializer):

    amount = serializers.CharField()
    facture = serializers.CharField()
    member_login = serializers.CharField()


class AccountsHistorySerializer(serializers.Serializer):

    account_type = serializers.CharField()
    login_bdc = serializers.CharField(required=False)
    cyclos_mode = serializers.CharField(required=False)
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
    porteur = serializers.CharField(required=False)
    selected_payments = serializers.ListField()


class SortieRetourEuskoSerializer(serializers.Serializer):
    deposit_amount = serializers.CharField()
    login_bdc = serializers.CharField()
    porteur = serializers.CharField()
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


class PaymentsAvailableEntreeStockSerializer(serializers.Serializer):
    login_bdc = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    cyclos_mode = serializers.CharField(required=False)
    old_password = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()
