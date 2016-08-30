import {
    fetchAuth,
    getAPIBaseURL,
    NavbarTitle,
    SelectizeUtils
} from 'Utils'

const {
    Row
} = FRC

import ReactSelectize from 'react-selectize'
const SimpleSelect = ReactSelectize.SimpleSelect

import classNames from 'classnames'

const {
    ToastContainer
} = ReactToastr
const ToastMessageFactory = React.createFactory(ReactToastr.ToastMessage.animation)


const MemberSubscriptionForm = React.createClass({

    mixins: [FRC.ParentContextMixin],

    propTypes: {
        children: React.PropTypes.node
    },

    render() {
        return (
            <Formsy.Form
                className={this.getLayoutClassName()}
                {...this.props}
                ref="memberaddsubscription"
            >
                {this.props.children}
            </Formsy.Form>
        );
    }
});

class MemberSubscriptionPage extends React.Component {

    constructor(props) {
        super(props);

        // Default state
        this.state = {
            canSubmit: false,
            amount: undefined,
            amountCustom: false,
            amountInvalid: false,
            amountSearch: '',
            amountList: [{value: '5', label: '5 (bas revenus)'},
                         {value: '10', label: '10 (cotisation classique)'},
                         {value: '20', label: '20 (cotisation de soutien)'},
                         {value: '21 ou +', label: 'ou +'}],
            memberID: document.getElementById("member_id").value,
            member: undefined,
            paymentMode: '',
            paymentModeList: undefined
        }

        // Get member data
        fetch(getAPIBaseURL + "members/" + this.state.memberID + '/',
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
            this.setState({member: json})
        })
        .catch(err => {
            // Error during request, or parsing NOK :(
            console.log(this.props.url, err)
        })

        // Get payment_modes
        var computePaymentModes = (paymentModes) => {
            this.setState({paymentModeList: paymentModes})
        }
        fetchAuth(getAPIBaseURL + "payment-modes/", 'get', computePaymentModes)
    }

    enableButton = () => {
        this.setState({canSubmit: true});
    }

    disableButton = () => {
        this.setState({canSubmit: false});
    }

    submitForm = (data) => {
        data = {amount: this.state.amount.value,
                payment_mode: this.state.paymentMode.value,
                member_id: document.getElementById("member_id").value}

        var computeForm = (data) => {
            console.log(data)
            this.setState({data: data})
            this.refs.container.success(
                __("L'enregistrement de la cotisation s'est déroulée correctement."),
                "",
                {
                    timeOut: 5000,
                    extendedTimeOut: 10000,
                    closeButton:true
                }
            )
        }

        var promiseError = (err) => {
            // Error during request, or parsing NOK :(
            console.log(this.props.url, err)
            this.refs.container.error(
                __("Une erreur s'est produite lors de l'enregistrement de la cotisation !"),
                "",
                {
                    timeOut: 5000,
                    extendedTimeOut: 10000,
                    closeButton:true
                }
            )
        }
        fetchAuth(this.props.url, this.props.method, computeForm, data, promiseError)
    }

    validateForm = () => {
        if (this.state.amount && this.state.paymentMode && !this.state.amountInvalid)
            this.enableButton()
        else
            this.disableButton()
    }

    // amount
    amountCreateFromSearch = (options, search) => {
        // Pretty much self explanatory:
        // this function is called when we start typing inside the select
        if (search)
            return {label: search, value: search}
        else
            return null
    }

    amountOnSearchChange = (search) => {
        this.setState({amountSearch: search})
    }

    amountRenderOption = (item) => {
        // This is how the list itself is displayed
        return  <div className="simple-option" style={{display: "flex", alignItems: "center"}}>
                    <div className="memberaddform" style={{marginLeft: 10}}>
                        {item.label}
                    </div>
                </div>
    }

    amountRenderValue = (item) => {
        // When we select a value, this is how we display it
        var divClass = classNames({
            'memberaddform': true,
            'has-error-value': this.state.amountInvalid,
        })

        return  <div className="simple-value">
                    <span className={divClass} style={{marginLeft: 10, verticalAlign: "middle"}}>
                        {item.value}
                    </span>
                </div>
    }

    amountOnValueChange = (item) => {
        if (item) {
            this.setState({amount: item, amountCustom: false})

            if (item.newOption) {
                this.setState({amountCustom: true})

                const re = new RegExp('^[0-9]+$')
                if (item.value < 20 || !re.test(item.value))
                    this.setState({amountInvalid: true})
                else
                    this.setState({amountInvalid: false})
            }
        }
        else {
            this.setState({amount: undefined, amountInvalid: false})
        }

        this.validateForm()
    }

    // paymentMode
    paymentModeRenderOption = (item) => {
        // This is how the list itself is displayed
        return  <div className="simple-option" style={{display: "flex", alignItems: "center"}}>
                    <div className="memberaddform" style={{marginLeft: 10}}>
                        {item.label}
                    </div>
                </div>
    }

    paymentModeRenderValue = (item) => {
        // When we select a value, this is how we display it
        return  <div className="simple-value">
                    <span className="memberaddform" style={{marginLeft: 10, verticalAlign: "middle"}}>
                        {item.label}
                    </span>
                </div>
    }

    paymentModeOnValueChange = (item) => {
        if (item)
            this.setState({paymentMode: item})
        else
            this.setState({paymentMode: undefined})

        this.validateForm()
    }

    render = () => {
        var divAmountClass = classNames({
            'form-group row': true,
            'has-error has-feedback': this.state.amountInvalid,
        })

        var reactSelectizeErrorClass = classNames({
            'has-error has-feedback': this.state.amountInvalid,
        })

        if (this.state.amountInvalid)
            var spanInvalidAmount = (
                <span className="help-block validation-message">
                    {__("Montant personnalisé incorrect, choisissez un montant dans la liste ou un montant supérieur à 20 (€ ou euskos)")}
                </span>)
        else
            var spanInvalidAmount = null

        if (this.state.member) {
            var memberName = this.state.member.firstname + " " + this.state.member.lastname
        }
        else {
            var memberName = null
        }

        return (
            <div className="row">
                <MemberSubscriptionForm
                    onValidSubmit={this.submitForm}
                    onInvalid={this.disableButton}
                    onValid={this.enableButton}
                    ref="memberaddsubscription">
                    <fieldset>
                        <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                htmlFor="memberaddsubscription-fullname">
                                {__("Nom complet")}
                            </label>
                            <div className="col-sm-6 memberaddsubscription control-label text-align-left"
                                 data-eusko="memberaddsubscription-fullname">
                                {memberName}
                            </div>
                            <div className="col-sm-3"></div>
                        </div>
                        <div className={divAmountClass}>
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddsubscription-amount">
                                {__("Montant")}
                                <span className="required-symbol">&nbsp;*</span>
                            </label>
                            <div className="col-sm-6 memberaddsubscription" data-eusko="memberaddsubscription-amount">
                                <SimpleSelect
                                    className={reactSelectizeErrorClass}
                                    ref="select"
                                    value={this.state.amount}
                                    search={this.state.amountSearch}
                                    options={this.state.amountList}
                                    placeholder={__("Montant de la cotisation")}
                                    theme="bootstrap3"
                                    createFromSearch={this.amountCreateFromSearch}
                                    onSearchChange={this.amountOnSearchChange}
                                    onValueChange={this.amountOnValueChange}
                                    renderOption={this.amountRenderOption}
                                    renderValue={this.amountRenderValue}
                                    onBlur={this.validateForm}
                                    required
                                />
                                { spanInvalidAmount }
                            </div>
                            <div className="col-sm-3"></div>
                        </div>
                        <div className="form-group row">
                            <label
                                className="control-label col-sm-3"
                                data-required="true"
                                htmlFor="memberaddsubscription-payment_mode">
                                {__("Mode de paiement")}
                                <span className="required-symbol">&nbsp;*</span>
                            </label>
                            <div className="col-sm-6 memberaddsubscription" data-eusko="memberaddsubscription-payment_mode">
                                <SimpleSelect
                                    className={reactSelectizeErrorClass}
                                    ref="select"
                                    value={this.state.paymentMode}
                                    options={this.state.paymentModeList}
                                    placeholder={__("Mode de paiement")}
                                    theme="bootstrap3"
                                    onValueChange={this.paymentModeOnValueChange}
                                    renderOption={this.paymentModeRenderOption}
                                    renderValue={this.paymentModeRenderValue}
                                    onBlur={this.validateForm}
                                    renderNoResultsFound={SelectizeUtils.selectizeNoResultsFound}
                                    required
                                />
                            </div>
                            <div className="col-sm-3"></div>
                        </div>
                    </fieldset>
                    <fieldset>
                        <Row layout="horizontal">
                            <input
                                name="submit"
                                data-eusko="memberaddsubscription-submit"
                                type="submit"
                                defaultValue="Enregistrer la cotisation"
                                className="btn btn-success"
                                formNoValidate={true}
                                disabled={!this.state.canSubmit}
                            />
                        </Row>
                    </fieldset>
                </MemberSubscriptionForm>
                <ToastContainer ref="container"
                                toastMessageFactory={ToastMessageFactory}
                                className="toast-top-right toast-top-right-navbar" />
            </div>
        );
    }
}


ReactDOM.render(
    <MemberSubscriptionPage url={getAPIBaseURL + "members-subscriptions/"} method="POST" />,
    document.getElementById('member-add-subscription')
)

ReactDOM.render(
    <NavbarTitle title={__("Enregistrement d'une cotisation")} />,
    document.getElementById('navbar-title')
)