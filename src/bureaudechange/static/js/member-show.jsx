import {
    checkStatus,
    parseJSON,
    titleCase,
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
            if (moment.unix(this.state.member.datefin) > moment())
                var memberStatus = (
                    <a href={"/members/subscription/add/" + this.state.member.id}
                       className="btn btn-success member-show-statut" data-eusko="member-show-statut">
                        {__("À jour")}
                    </a>
                )
            else
                var memberStatus = (
                    <a href={"/members/subscription/add/" + this.state.member.id}
                       className="btn btn-warning member-show-statut"
                       data-eusko="member-show-statut">
                        {__("Pas à jour")}
                    </a>
                )

            if (this.state.member.login.startsWith("Z", 0))
                var memberName = (
                    <div className="col-sm-4" >
                        <span className="member-show-societe">{this.state.member.societe}</span>
                    </div>
                )
            else
                var memberName = (
                    <div className="col-sm-4" >
                        <span className="member-show-civility">{titleCase(this.state.member.civility_id) + " "}</span>
                        <span data-eusko="member-show-fullname">
                            {this.state.member.firstname + " " + this.state.member.lastname}
                        </span>
                    </div>
                )

            if (this.state.member.address)
                var memberAddress = (
                    <span data-eusko="member-show-address">
                        {this.state.member.address + "  ―  " + this.state.member.zip + " " + this.state.member.town}
                    </span>
                )
            else
                var memberAddress = (
                    <span data-eusko="member-show-address">
                        {this.state.member.zip + " " + this.state.member.town}
                    </span>
                )

            var memberData = (
                <div className="row">
                    <div className="panel panel-primary member-show-panel">
                        <div className="panel-body">
                            <div className="form-group row">
                                <label className="control-label col-sm-2">{__("N° Adhérent")}</label>
                                <div className="col-sm-4">
                                    <span data-eusko="member-show-login">{this.state.member.login}</span>
                                </div>
                                <div className="col-sm-6">
                                    {memberStatus}
                                </div>
                            </div>
                            <div className="form-group row">
                                <label className="control-label col-sm-2">{__("Nom complet")}</label>
                                {memberName}
                                <div className="col-sm-6">
                                </div>
                            </div>
                            <div className="form-group row">
                                <label className="control-label col-sm-2">{__("Adresse postale")}</label>
                                <div className="col-sm-8" >
                                    {memberAddress}
                                </div>
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