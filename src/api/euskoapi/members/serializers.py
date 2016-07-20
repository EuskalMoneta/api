from rest_framework import serializers


class ArrayOptionsSerializer(serializers.Serializer):

    options_communaute_communes = serializers.CharField()
    options_bureau_de_change = serializers.CharField()
    options_recevoir_actus = serializers.BooleanField()
    options_supplement_2_euros = serializers.BooleanField()
    options_prelevement_auto_cotisation = serializers.BooleanField()
    options_promesse_change_mensuel_eusko_numerique = serializers.FloatField()


class MemberSerializer(serializers.Serializer):

    element = serializers.CharField()
    table_element = serializers.CharField()
    mesgs = serializers.CharField(allow_null=True)
    login = serializers.CharField()
    # pass = serializers.CharField(allow_null=True)
    societe = serializers.CharField()
    company = serializers.CharField()
    address = serializers.CharField()
    zip = serializers.CharField()
    town = serializers.CharField()
    state_id = serializers.CharField()
    state_code = serializers.CharField()
    state = serializers.CharField()
    email = serializers.CharField()
    skype = serializers.CharField()
    phone = serializers.CharField(allow_null=True)
    phone_perso = serializers.CharField(allow_null=True)
    phone_mobile = serializers.CharField(allow_null=True)
    morphy = serializers.CharField()
    public = serializers.CharField()
    statut = serializers.CharField()
    photo = serializers.CharField(allow_null=True)
    datec = serializers.IntegerField()
    datem = serializers.IntegerField()
    datefin = serializers.IntegerField()
    datevalid = serializers.CharField()
    birth = serializers.CharField()
    typeid = serializers.CharField()
    type = serializers.CharField()
    need_subscription = serializers.IntegerField()
    user_id = serializers.CharField(allow_null=True)
    user_login = serializers.CharField(allow_null=True)
    fk_soc = serializers.CharField()
    fk_asso = serializers.CharField()

    # DateTimeField example 2016-01-01 00:00:00
    first_subscription_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    first_subscription_amount = serializers.CharField()
    last_subscription_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    last_subscription_date_start = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    last_subscription_date_end = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    last_subscription_amount = serializers.CharField()

    entity = serializers.CharField()
    id = serializers.CharField()
    error = serializers.CharField(allow_null=True)
    # errors = []
    import_key = serializers.CharField(allow_null=True)
    array_options = ArrayOptionsSerializer()
    # linkedObjectsIds = allow_null=True  # noqa
    # linkedObjects = allow_null=True  # noqa
    # context = []
    canvas = serializers.CharField(allow_null=True)
    # project = allow_null=True  # noqa
    # fk_project = allow_null=True  # noqa
    # projet = allow_null=True  # noqa
    # contact = allow_null=True  # noqa
    # contact_id = allow_null=True  # noqa
    # thirdparty = allow_null=True  # noqa
    # client = allow_null=True  # noqa
    # user = allow_null=True  # noqa
    # origin = allow_null=True  # noqa
    # origin_id = allow_null=True  # noqa
    ref = serializers.CharField()
    # ref_previous = allow_null=True  # noqa
    # ref_next = allow_null=True  # noqa
    ref_ext = serializers.CharField(allow_null=True)
    # table_element_line = allow_null=True  # noqa
    country = serializers.CharField()
    country_id = serializers.CharField()
    country_code = serializers.CharField()
    # barcode_type = allow_null=True  # noqa
    # barcode_type_code = allow_null=True  # noqa
    # barcode_type_label = allow_null=True  # noqa
    # barcode_type_coder = allow_null=True  # noqa
    # mode_reglement_id = allow_null=True  # noqa
    # cond_reglement_id = allow_null=True  # noqa
    # cond_reglement = allow_null=True  # noqa
    # fk_delivery_address = allow_null=True  # noqa
    # shipping_method_id = allow_null=True  # noqa
    # modelpdf = allow_null=True  # noqa
    # fk_account = allow_null=True  # noqa
    note_public = serializers.CharField(allow_null=True)
    note_private = serializers.CharField(allow_null=True)
    # note = allow_null=True  # noqa
    # total_ht = allow_null=True  # noqa
    # total_tva = allow_null=True  # noqa
    # total_localtax1 = allow_null=True  # noqa
    # total_localtax2 = allow_null=True  # noqa
    # total_ttc = allow_null=True  # noqa
    # lines = allow_null=True  # noqa
    # fk_incoterms = allow_null=True  # noqa
    # libelle_incoterms = allow_null=True  # noqa
    # location_incoterms = allow_null=True  # noqa
    name = serializers.CharField(allow_null=True)
    lastname = serializers.CharField()
    firstname = serializers.CharField()
    civility_id = serializers.CharField()
