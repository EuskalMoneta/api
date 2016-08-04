import { checkStatus, parseJSON } from 'Utils'

const { Input, RadioGroup, Row } = FRC

import DatePicker from 'react-datepicker'
require('react-datepicker/dist/react-datepicker.css')

var { ToastContainer } = ReactToastr
var ToastMessageFactory = React.createFactory(ReactToastr.ToastMessage.animation)

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

Formsy.addValidationRule('isFrenchPhoneNumber', (values, value) =>
{
    if (!value) {
        return false;
    }

    if (value.startsWith("0", 0) && value.length === 10) {
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
            birth: moment().set({'year': 1980, 'month': 0, 'date': 1})  // !! month 0 = January
        }
    }

    enableButton = () => {
        this.setState({
            canSubmit: true
        });
    }

    disableButton = () => {
        this.setState({
            canSubmit: false
        });
    }

    handleBirthChange = (date) => {
        this.setState({
            birth: date
        });
    }

    submitForm = (data) => {
        // We push the 'birth' field into the data passed to the server
        data['birth'] = this.state.birth.format('DD/MM/YYYY')

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
            this.setState({data: json.results})
            this.refs.container.success(
                __("La création de l'adhérent s'est déroulée correctement."),
                "",
                {
                    timeOut: 3000,
                    extendedTimeOut: 10000,
                    closeButton:true
                }
            )
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
                <div className="page-header">
                    <h1>{__("Adhésion")}</h1>
                </div>
                <MemberAddForm
                    onValidSubmit={this.submitForm}
                    onInvalid={this.disableButton}
                    onValid={this.enableButton}
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
                            required
                        />
                        <Input
                            name="lastname"
                            data-eusko="memberaddform-lastname"
                            value=""
                            label={__("Nom")}
                            type="text"
                            placeholder={__("Nom")}
                            required
                        />
                        <Input
                            name="firstname"
                            data-eusko="memberaddform-firstname"
                            value=""
                            label={__("Prénom")}
                            type="text"
                            placeholder={__("Prénom")}
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
                            <div className="col-sm-9 memberaddform-birth" data-eusko="memberaddform-birth">
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
                            required
                        />
                        <Input
                            name="zip"
                            data-eusko="memberaddform-zip"
                            value=""
                            label={__("Code Postal")}
                            type="text"
                            placeholder={__("Code Postal")}
                            required
                        />
                        <Input
                            name="town"
                            data-eusko="memberaddform-town"
                            value=""
                            label={__("Ville")}
                            type="text"
                            placeholder={__("Ville")}
                            required
                        />
                        <Input
                            name="country_id"
                            data-eusko="memberaddform-country_id"
                            value=""
                            label={__("Pays")}
                            type="text"
                            placeholder={__("Pays")}
                            required
                        />
                        <Input
                            name="phone"
                            data-eusko="memberaddform-phone"
                            value=""
                            label={__("N° téléphone")}
                            help={__("Format: 0612345678")}
                            type="tel"
                            placeholder={__("N° téléphone")}
                            validations="isFrenchPhoneNumber"
                            validationErrors={{
                                isFrenchPhoneNumber: __("Ceci n'est pas un N° téléphone valide. Exemple: 0612345678.")
                            }}
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
                            required
                        />
                    </fieldset>
                    <fieldset>
                        <Row layout="horizontal">
                            <input
                                name="submit"
                                data-eusko="memberaddform-submit"
                                type="submit"
                                defaultValue={__("Envoyer")}
                                className="btn btn-primary"
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
    <MemberAddPage url="http://localhost:8000/members/" method="POST" />,
    document.getElementById('member-add')
);