import { checkStatus, parseJSON } from 'Utils'

const { Input, Row } = FRC


const MemberSearchForm = React.createClass({

    mixins: [FRC.ParentContextMixin],

    propTypes: {
        children: React.PropTypes.node
    },

    render() {
        return (
            <Formsy.Form
                className={this.getLayoutClassName()}
                {...this.props}
                ref="membersearch"
            >
                {this.props.children}
            </Formsy.Form>
        );
    }
});

class MemberSearchPage extends React.Component {

    constructor(props) {
        super(props);

        // Default state
        this.state = {
            canSubmit: false
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

    getOptions = (input) => {
      return
        fetch(this.props.search_url,
        {
            body: JSON.stringify(input),
            method: 'get',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        })
        .then(checkStatus)
        .then(parseJSON)
        .then((json) => {
          return { options: json };
        })
    }

    submitForm = (data) => {
        data = {amount,
                label}

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
                "L'enregistrement de la cotisation s'est déroulée correctement.",
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
                "Une erreur s'est produite lors de la création de l'adhérent !",
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
                    <h1>Recherche d'un adhérent</h1>
                </div>
                <MemberSearchForm
                    onValidSubmit={this.submitForm}
                    onInvalid={this.disableButton}
                    onValid={this.enableButton}
                    ref="membersearch">
                    <fieldset>
                        <Select.Async
                            data-eusko="membersearch-search"
                            name="search"
                            value="one"
                            loadOptions={this.getOptions}
                        />
                    </fieldset>
                    <fieldset>
                        <Row layout="horizontal">
                            <input
                                name="submit"
                                data-eusko="membersearch-submit"
                                type="submit"
                                defaultValue="Sélection d'un adhérent"
                                className="btn btn-success"
                                formNoValidate={true}
                                disabled={!this.state.canSubmit}
                            />
                        </Row>
                    </fieldset>
                </MemberSearchForm>
            </div>
        );
    }
}


ReactDOM.render(
    <MemberSearchPage
        url="http://localhost:8000/members-subsubscriptions"
        search_url="http://localhost:8000/members-search"
        method="POST"
    />,
    document.getElementById('member-search')
);