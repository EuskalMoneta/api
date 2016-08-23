import {
    checkStatus,
    parseJSON,
    getAPIBaseURL,
    NavbarTitle
} from 'Utils'


const MemberShow = React.createClass({

    componentWillMount: function() {
        this.state = {
            memberID: document.getElementById("member_id").value,
            member: undefined
        }

        // Get member data
        fetch(this.props.url + this.state.memberID + '/',
        {
            method: this.props.method,
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
    },

    render: function() {
        if (this.state.member) {
                var memberData = (
                    <div className="row">
                        <div className="panel panel-info">
                            <div className="panel-body">
                                <div className="row">
                                    <span className="login">{this.state.member.login}</span>
                                </div>
                                <div className="row">
                                    <span className="firstname">{this.state.member.firstname}</span>
                                    <span className="lastname">{this.state.member.lastname}</span>
                                </div>
                                <div className="row">
                                    <span className="address">{this.state.member.address}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )
        }
        else
            var memberData = null

        return memberData
    }
})


ReactDOM.render(
    <MemberShow url={getAPIBaseURL + "members/"} method="GET" />,
    document.getElementById('member-show')
)

ReactDOM.render(
    <NavbarTitle title={__("Fiche adhérent")} />,
    document.getElementById('navbar-title')
)