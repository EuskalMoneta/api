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
});

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
                "La création de l'adhérent s'est déroulée correctement.",
                {
                    timeOut: 3000,
                    extendedTimeOut: 10000,
                    closeButton:true
                }
            )
        })
        .catch(err => {
            // Error during request, or parsing NOK :(
            console.error(this.props.url, err)
            this.refs.container.error(
                "Une erreur s'est produite lors de la création de l'adhérent !",
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
                    <h1>Adhésion</h1>
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
                            label="N° adhérent (Exxxxx)"
                            type="text"
                            placeholder="N° adhérent (Exxxxx)"
                            validations="isMemberIdEusko"
                            validationErrors={{
                                isMemberIdEusko: "Ceci n'est pas un N° adhérent Eusko valide."
                            }}
                            required
                        />
                    </fieldset>
                    <fieldset>
                        <RadioGroup
                            name="civility_id"
                            data-eusko="memberaddform-civility_id"
                            type="inline"
                            label="Civilité"
                            options={[{value: 'MME', label: 'Madame'},
                                     {value: 'MR', label: 'Monsieur'}
                            ]}
                            required
                        />
                        <Input
                            name="lastname"
                            data-eusko="memberaddform-lastname"
                            value=""
                            label="Nom"
                            type="text"
                            placeholder="Nom"
                            required
                        />
                        <Input
                            name="firstname"
                            data-eusko="memberaddform-firstname"
                            value=""
                            label="Prénom"
                            type="text"
                            placeholder="Prénom"
                            required
                        />
                       <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddform-birth">
                                Date de naissance
                                <span className="required-symbol">&nbsp;*</span>
                            </label>
                            <div className="col-sm-9 memberaddform-birth" data-eusko="memberaddform-birth">
                                <DatePicker
                                    name="birth"
                                    className="form-control"
                                    placeholderText="Date de naissance"
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
                            label="Adresse postale"
                            type="text"
                            placeholder="Adresse postale"
                            required
                        />
                        <Input
                            name="town"
                            data-eusko="memberaddform-town"
                            value=""
                            label="Ville"
                            type="text"
                            placeholder="Ville"
                            required
                        />
                        <Input
                            name="zip"
                            data-eusko="memberaddform-zip"
                            value=""
                            label="Code Postal"
                            type="text"
                            placeholder="Code Postal"
                            required
                        />
                        <Input
                            name="state_id"
                            data-eusko="memberaddform-state_id"
                            value=""
                            label="Département"
                            type="text"
                            placeholder="Département"
                            required
                        />
                        <Input
                            name="country_id"
                            data-eusko="memberaddform-country_id"
                            value=""
                            label="Pays"
                            type="text"
                            placeholder="Pays"
                            required
                        />
                        <Input
                            name="phone"
                            data-eusko="memberaddform-phone"
                            value=""
                            label="N° téléphone"
                            type="tel"
                            placeholder="N° téléphone"
                            validations="isFrenchPhoneNumber"
                            validationErrors={{
                                isFrenchPhoneNumber: "Ceci n'est pas un N° téléphone valide."
                            }}
                            required
                        />
                        <Input
                            name="email"
                            data-eusko="memberaddform-email"
                            value=""
                            label="Email"
                            type="email"
                            placeholder="Email de l'adhérent"
                            validations="isEmail"
                            validationErrors={{
                                isEmail: "Adresse email non valide"
                            }}
                            required
                        />
                        <RadioGroup
                            name="options_recevoir_actus"
                            data-eusko="memberaddform-options-recevoir-actus"
                            type="inline"
                            label="Souhaite être informé des actualités liées à l'eusko"
                            help="L'adhérent recevra un à deux mails par semaine."
                            options={[{value: '1', label: 'Oui'},
                                      {value: '0', label: 'Non'}
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
                                defaultValue="Envoyer"
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