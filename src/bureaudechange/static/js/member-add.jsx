import { checkStatus, parseJSON, getAPIBaseURL, NavbarTitle } from 'Utils'

const { Input, RadioGroup, Row } = FRC

import DatePicker from 'react-datepicker'
require('react-datepicker/dist/react-datepicker.css')

import ReactSelectize from 'react-selectize'
const SimpleSelect = ReactSelectize.SimpleSelect

const { ToastContainer } = ReactToastr
const ToastMessageFactory = React.createFactory(ReactToastr.ToastMessage.animation)


Formsy.addValidationRule('isMemberIdEusko', (values, value) =>
{
    if (!value) {
        return false;
    }

    if (value.startsWith("E", 0) && value.length === 6) {
        return true;
    }
    else {
        return false;
    }
});

Formsy.addValidationRule('isValidPhoneNumber', (values, value) =>
{
    if (!value) {
        return false;
    }

    if (value.indexOf('.') === -1 && value.indexOf(' ') === -1) {
        return true;
    }
    else {
        return false;
    }
});

const MemberAddForm = React.createClass({

    mixins: [FRC.ParentContextMixin],

    propTypes: {
        children: React.PropTypes.node
    },

    render() {
        return (
            <Formsy.Form
                className={this.getLayoutClassName()}
                {...this.props}
                ref="memberaddform"
            >
                {this.props.children}
            </Formsy.Form>
        );
    }
})

class MemberAddPage extends React.Component {

    constructor(props) {
        super(props);

        // Default state
        this.state = {
            canSubmit: false,
            validFields: false,
            validCustomFields: false,
            country: undefined,
            zip: undefined,
            zipSearch: undefined,
            zipList: undefined,
            town: undefined,
            townList: undefined,
            birth: moment().set({'year': 1980, 'month': 0, 'date': 1}),  // !! month 0 = January
            assoSaisieLibre: false,
            fkAsso: undefined,
            fkAsso2: undefined,
            fkAssoAllList: undefined,
            fkAssoApprovedList: undefined
        }

        // Get countries for the country selector
        fetch(getAPIBaseURL + "countries/",
        {
            method: 'get',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        })
        .then(checkStatus)
        .then(parseJSON)
        .then(json => {
            var france = _.findWhere(json, {label: "France"})
            var france = {label: "France", value: france.id}

            var res = _.chain(json)
                .filter(function(item){ return item.active == 1 && item.code != "" &&  item.label != "France" })
                .map(function(item){ return {label: item.label, value: item.id} })
                .sortBy(function(item){ return item.label })
                .value()

            // We add France at first position of the Array, and we set it as the default value
            res.unshift(france)
            this.setState({countries: res, country: france})
        })
        .catch(err => {
            // Error during request, or parsing NOK :(
            console.log(this.props.url, err)
        })

        // Get all associations (no filter): fkAssoAllList
        fetch(getAPIBaseURL + "associations/",
        {
            method: 'get',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        })
        .then(checkStatus)
        .then(parseJSON)
        .then(json => {
            var res = _.chain(json)
                .map(function(item){ return {label: item.nom, value: item.id} })
                .sortBy(function(item){ return item.label })
                .value()

            this.setState({fkAssoAllList: res})
        })
        .catch(err => {
            // Error during request, or parsing NOK :(
            console.log(this.props.url, err)
        })

        // Get only approved associations: fkAssoApprovedList
        fetch(getAPIBaseURL + "associations/?approved=yes",
        {
            method: 'get',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        })
        .then(checkStatus)
        .then(parseJSON)
        .then(json => {
            var res = _.chain(json)
                .map(function(item){ return {label: item.nom, value: item.id} })
                .sortBy(function(item){ return item.label })
                .value()

            this.setState({fkAssoApprovedList: res})
        })
        .catch(err => {
            // Error during request, or parsing NOK :(
            console.log(this.props.url, err)
        })
    }

    handleBirthChange = (date) => {
        this.setState({birth: date});
    }

    // generic callback for all selectize objects
    selectizeCreateFromSearch = (options, search) => {
        // Pretty much self explanatory:
        // this function is called when we start typing inside the select
        if (search)
        {
            if (search.length == 0 || (options.map(function(option)
            {
                return option.label;
            })).indexOf(search) > -1)
                return null;
            else
                return {label: search, value: search};
        }
        else
            return null;
    }

    selectizeRenderOption = (item) => {
        // This is how the list itself is displayed
        return  <div className="simple-option" style={{display: "flex", alignItems: "center"}}>
                    <div className="memberaddform" style={{marginLeft: 10}}>
                        {item.label}
                    </div>
                </div>
    }

    selectizeNewRenderOption = (item) => {
        // This is how the list itself is displayed
        return  <div className="simple-option" style={{display: "flex", alignItems: "center"}}>
                    <div className="memberaddform" style={{marginLeft: 10}}>
                        {!!item.newOption ? __("Ajouter") + " " + item.label + " ..." : item.label}
                    </div>
                </div>
    }

    selectizeRenderValue = (item) => {
        // When we select a value, this is how we display it
        return  <div className="simple-value">
                    <span className="memberaddform" style={{marginLeft: 10, verticalAlign: "middle"}}>{item.label}</span>
                </div>
    }

    selectizeNoResultsFound = () => {
        return  <div className="no-results-found" style={{fontSize: 15}}>
                    {__("Pas de résultat")}
                </div>
    }

    // zip
    zipOnSearchChange = (search) => {
        this.setState({zipSearch: search})
        // Search for towns for this zipcode for France only
        if (search.length >= 4 && this.state.country.label == "France") {
            // We use fetch API to ... fetch towns for this zipcode
            fetch(getAPIBaseURL + "towns/?zipcode=" + search,
            {
                method: 'get',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            })
            .then(checkStatus)
            .then(parseJSON)
            .then(json => {
                var zipList = _.chain(json)
                    .map(function(item){ return {label: item.zip + " - " + item.town, value: item.zip, town: item.town} })
                    .sortBy(function(item){ return item.label })
                    .value()

                var townList = _.chain(json)
                    .map(function(item){ return {label: item.town, value: item.town} })
                    .sortBy(function(item){ return item.label })
                    .value()

                this.setState({zipList: zipList, townList: townList})
            })
            .catch(err => {
                // Error during request, or parsing NOK :(
                console.log(getAPIBaseURL + "towns/?zipcode=" + search, err)
            })
        }
    }

    zipRenderNoResultsFound = (item, search) => {
        var message = ""

        // We have a search term (not empty)
        if (search)
        {
            // We have a sinificative search term
            if (search.length < 4)
                message = __("Taper 4 chiffres minimum ...")
            else
            {
                // We have a positive result (zip+town list) for this search term
                if (this.state.zipList == undefined)
                    message = __("Pas de résultat")
            }
        }
        else
            message = __("Taper 4 chiffres minimum ...")

        if (message) {
            return  <div className="no-results-found" style={{fontSize: 15}}>
                        {message}
                    </div>
        }
    }

    zipOnValueChange = (item) => {
        if (item) {
            this.setState({zip: item, town: {label: item.town, value: item.town}})
        }
        else
            this.setState({zip: undefined, town: undefined})
    }

    zipRenderValue = (item) => {
        // When we select a value, this is how we display it
        return  <div className="simple-value">
                    <span className="memberaddform" style={{marginLeft: 10, verticalAlign: "middle"}}>{item.value}</span>
                </div>
    }

    zipOnBlur = () => {
        this.setState({zipList: undefined, townList: undefined})
        this.validateFormOnBlur()
    }

    // town
    townOnValueChange = (item) => {
        this.setState({town: item})
    }

    // country
    countryOnValueChange = (item) => {
        this.setState({country: item})
    }

    // fkasso
    fkAssoOnValueChange = (item) => {
        if (item) {
            if (item.newOption)
                this.setState({assoSaisieLibre: true})
            this.setState({fkAsso: item})
        }
        else {
            this.setState({assoSaisieLibre: false})
            this.setState({fkAsso: undefined})
        }
    }

    // fkasso2
    fkAsso2OnValueChange = (item) => {
        this.setState({fkAsso2: item})
    }


    enableButton = () => {
        this.setState({canSubmit: true});
    }

    disableButton = () => {
        this.setState({canSubmit: false});
    }

    validFields = () => {
        this.setState({validFields: true});

        if (this.state.validCustomFields)
            this.enableButton()
    }

    validateFormOnBlur = () => {
        if (this.state.birth && this.state.zip && this.state.town && this.state.country)
        {
            this.setState({validCustomFields: true})

            if (this.state.validFields)
                this.enableButton()
        }
        else
            this.disableButton()
    }

    submitForm = (data) => {
        // We push custom fields (like DatePickers, Selectize, ...) into the data passed to the server
        data['birth'] = this.state.birth.format('DD/MM/YYYY')
        data['country_id'] = this.state.country.value
        data['zip'] = this.state.zip.value
        data['town'] = this.state.town.value

        // We need to verify whether we are in "saisie libre" or not
        if (this.state.fkAsso) {
            if (this.state.assoSaisieLibre)
                data['options_asso_saisie_libre'] = this.state.fkAsso.value
            else
                data['fk_asso'] = this.state.fkAsso.value
        }

        if (this.state.fkAsso2)
            data['fk_asso_2'] = this.state.fkAsso2.value

        console.log(data)
        fetch(this.props.url,
        {
            body: JSON.stringify(data),
            method: this.props.method,
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        })
        .then(checkStatus)
        .then(parseJSON)
        .then(json => {
            console.log(json)
            this.refs.container.success(
                __("La création de l'adhérent s'est déroulée correctement."),
                "",
                {
                    timeOut: 3000,
                    extendedTimeOut: 10000,
                    closeButton:true
                }
            )
            // redirect to create subscription page in 3 seconds
            setTimeout(() => window.location.assign("/members/subscription/add/" + json), 3000)
        })
        .catch(err => {
            // Error during request, or parsing NOK :(
            console.log(this.props.url, err)
            this.refs.container.error(
                __("Une erreur s'est produite lors de la création de l'adhérent !"),
                "",
                {
                    timeOut: 3000,
                    extendedTimeOut: 10000,
                    closeButton:true
                }
            )
        })
    }

    render = () => {

        return (
            <div className="row">
                <MemberAddForm
                    onValidSubmit={this.submitForm}
                    onInvalid={this.disableButton}
                    onValid={this.validFields}
                    ref="memberaddform">
                    <fieldset>
                        <Input
                            name="login"
                            data-eusko="memberaddform-login"
                            value=""
                            label={__("N° adhérent")}
                            type="text"
                            placeholder={__("N° adhérent")}
                            help={__("Format: E12345")}
                            validations="isMemberIdEusko"
                            validationErrors={{
                                isMemberIdEusko: __("Ceci n'est pas un N° adhérent Eusko valide.")
                            }}
                            elementWrapperClassName={[{'col-sm-9': false}, 'col-sm-6']}
                            required
                        />
                        <RadioGroup
                            name="civility_id"
                            data-eusko="memberaddform-civility_id"
                            type="inline"
                            label={__("Civilité")}
                            options={[{value: 'MME', label: __('Madame')},
                                     {value: 'MR', label: __('Monsieur')}
                            ]}
                            elementWrapperClassName={[{'col-sm-9': false}, 'col-sm-6']}
                            required
                        />
                        <Input
                            name="lastname"
                            data-eusko="memberaddform-lastname"
                            value=""
                            label={__("Nom")}
                            type="text"
                            placeholder={__("Nom")}
                            validations="maxLength:45"
                            validationErrors={{
                                maxLength: __("Ce champ ne peut pas faire plus de 45 caractères!")
                            }}
                            elementWrapperClassName={[{'col-sm-9': false}, 'col-sm-6']}
                            required
                        />
                        <Input
                            name="firstname"
                            data-eusko="memberaddform-firstname"
                            value=""
                            label={__("Prénom")}
                            type="text"
                            placeholder={__("Prénom")}
                            validations="maxLength:45"
                            validationErrors={{
                                maxLength: __("Ce champ ne peut pas faire plus de 45 caractères!")
                            }}
                            elementWrapperClassName={[{'col-sm-9': false}, 'col-sm-6']}
                            required
                        />
                        <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddform-birth">
                                {__("Date de naissance")}
                                <span className="required-symbol">&nbsp;*</span>
                            </label>
                            <div className="col-sm-6 memberaddform-birth" data-eusko="memberaddform-birth">
                                <DatePicker
                                    name="birth"
                                    className="form-control"
                                    placeholderText={__("Date de naissance")}
                                    selected={this.state.birth}
                                    onChange={this.handleBirthChange}
                                    showYearDropdown
                                    locale="fr"
                                    required
                                />
                            </div>
                        </div>
                        <Input
                            name="address"
                            data-eusko="memberaddform-address"
                            value=""
                            label={__("Adresse postale")}
                            type="text"
                            placeholder={__("Adresse postale")}
                            elementWrapperClassName={[{'col-sm-9': false}, 'col-sm-6']}
                            required
                        />
                        <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddform-zip">
                                {__("Code Postal")}
                                <span className="required-symbol">&nbsp;*</span>
                            </label>
                            <div className="col-sm-6 memberaddform" data-eusko="memberaddform-zip">
                                <SimpleSelect
                                    ref="select"
                                    value={this.state.zip}
                                    search={this.state.zipSearch}
                                    options={this.state.zipList}
                                    placeholder={__("Code Postal")}
                                    theme="bootstrap3"
                                    autocomplete="off"
                                    createFromSearch={this.selectizeCreateFromSearch}
                                    onSearchChange={this.zipOnSearchChange}
                                    onValueChange={this.zipOnValueChange}
                                    renderOption={this.selectizeRenderOption}
                                    renderValue={this.zipRenderValue}
                                    onBlur={this.zipOnBlur}
                                    renderNoResultsFound={this.zipRenderNoResultsFound}
                                    required
                                />
                            </div>
                        </div>
                        <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddform-town">
                                {__("Ville")}
                                <span className="required-symbol">&nbsp;*</span>
                            </label>
                            <div className="col-sm-6 memberaddform" data-eusko="memberaddform-town">
                                <SimpleSelect
                                    ref="select"
                                    value={this.state.town}
                                    options={this.state.townList}
                                    placeholder={__("Ville")}
                                    autocomplete="off"
                                    theme="bootstrap3"
                                    createFromSearch={this.selectizeCreateFromSearch}
                                    onValueChange={this.townOnValueChange}
                                    renderValue={this.selectizeRenderValue}
                                    onBlur={this.validateFormOnBlur}
                                    renderNoResultsFound={this.selectizeNoResultsFound}
                                    required
                                />
                            </div>
                        </div>
                        <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddform-country">
                                {__("Pays")}
                                <span className="required-symbol">&nbsp;*</span>
                            </label>
                            <div className="col-sm-6 memberaddform" data-eusko="memberaddform-country">
                                <SimpleSelect
                                    ref="select"
                                    value={this.state.country}
                                    options={this.state.countries}
                                    placeholder={__("Pays")}
                                    autocomplete="off"
                                    theme="bootstrap3"
                                    onValueChange={this.countryOnValueChange}
                                    renderOption={this.selectizeNewRenderOption}
                                    renderValue={this.selectizeRenderValue}
                                    onBlur={this.validateFormOnBlur}
                                    renderNoResultsFound={this.selectizeNoResultsFound}
                                    required
                                />
                            </div>
                        </div>
                        <Input
                            name="phone"
                            data-eusko="memberaddform-phone"
                            value=""
                            label={__("N° téléphone")}
                            type="tel"
                            placeholder={__("N° téléphone")}
                            validations="isValidPhoneNumber"
                            validationErrors={{
                                isValidPhoneNumber: __("Ceci n'est pas un N° téléphone valide. Evitez les points et les espaces.")
                            }}
                            elementWrapperClassName={[{'col-sm-9': false}, 'col-sm-6']}
                            required
                        />
                        <Input
                            name="email"
                            data-eusko="memberaddform-email"
                            value=""
                            label={__("Email")}
                            type="email"
                            placeholder={__("Email de l'adhérent")}
                            validations="isEmail"
                            validationErrors={{
                                isEmail: __("Adresse email non valide")
                            }}
                            elementWrapperClassName={[{'col-sm-9': false}, 'col-sm-6']}
                            required
                        />
                        <RadioGroup
                            name="options_recevoir_actus"
                            data-eusko="memberaddform-options-recevoir-actus"
                            type="inline"
                            label={__("Souhaite être informé des actualités liées à l'eusko")}
                            help={__("L'adhérent recevra un à deux mails par semaine.")}
                            options={[{value: '1', label: __('Oui')},
                                      {value: '0', label: __('Non')}
                            ]}
                            elementWrapperClassName={[{'col-sm-9': false}, 'col-sm-6']}
                            required
                        />
                        <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddform-town">
                                {__("Choix Association 3% #1")}
                            </label>
                            <div className="col-sm-6 memberaddform" data-eusko="memberaddform-town">
                                <SimpleSelect
                                    ref="select"
                                    value={this.state.fkAsso}
                                    options={this.state.fkAssoAllList}
                                    placeholder={__("Choix Association 3% #1")}
                                    theme="bootstrap3"
                                    help={__("Blabla")}
                                    createFromSearch={this.selectizeCreateFromSearch}
                                    onValueChange={this.fkAssoOnValueChange}
                                    renderValue={this.selectizeRenderValue}
                                    renderOption={this.selectizeNewRenderOption}
                                    onBlur={this.validateFormOnBlur}
                                />
                            </div>
                        </div>
                        <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddform-town">
                                {__("Choix Association 3% #2")}
                            </label>
                            <div className="col-sm-6 memberaddform" data-eusko="memberaddform-town">
                                <SimpleSelect
                                    ref="select"
                                    value={this.state.fkAsso2}
                                    options={this.state.fkAssoApprovedList}
                                    placeholder={__("Choix Association 3% #2")}
                                    theme="bootstrap3"
                                    help={__("Blabla")}
                                    onValueChange={this.fkAsso2OnValueChange}
                                    renderOption={this.selectizeRenderOption}
                                    renderValue={this.selectizeRenderValue}
                                    onBlur={this.validateFormOnBlur}
                                    renderNoResultsFound={this.selectizeNoResultsFound}
                                />
                            </div>
                        </div>
                    </fieldset>
                    <fieldset>
                        <Row layout="horizontal">
                            <input
                                name="submit"
                                data-eusko="memberaddform-submit"
                                type="submit"
                                defaultValue={__("Envoyer")}
                                className="btn btn-success"
                                formNoValidate={true}
                                disabled={!this.state.canSubmit}
                            />
                        </Row>
                    </fieldset>
                </MemberAddForm>
                <ToastContainer ref="container"
                                toastMessageFactory={ToastMessageFactory}
                                className="toast-top-right" />
            </div>
        );
    }
}


ReactDOM.render(
    <MemberAddPage url={getAPIBaseURL + "members/"} method="POST" />,
    document.getElementById('member-add')
)

ReactDOM.render(
    <NavbarTitle title={__("Adhésion")} />,
    document.getElementById('navbar-title')
)