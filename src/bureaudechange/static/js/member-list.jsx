const MemberList = React.createClass({
    getInitialState: function() {
        return {data: []};
    },
    componentDidMount: function() {
        fetch(this.props.url,
        {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        })
        .then(function(response) {
            return response.json()
        })
        .then(function(json) {
            this.setState({data: json.results})
        }.bind(this))
        .catch(function(err) {
            // Error during parsing :(
            console.error(this.props.url, err)
        }.bind(this))
    },
    render: function() {
        // loop over this.props.data
        var membersNodes = this.state.data.map(
            function(member) {
                return (
                    <Member lastname={member.lastname} firstname={member.firstname} email={member.email} key={member.id}></Member>
                );
            }
        );

        return (
            <table className="table table-striped table-hover">
            <thead>
                <tr>
                    <th>Nom</th>
                    <th>Prénom</th>
                    <th>Email</th>
                </tr>
            </thead>
            <tbody>
                {membersNodes}
            </tbody>
            </table>
        );
    }
});

const Member = React.createClass({
    render: function() {
        return (
            <tr>
                <td>{this.props.lastname}</td>
                <td>{this.props.firstname}</td>
                <td>{this.props.email}</td>
            </tr>
        );
    }
});

ReactDOM.render(
    <MemberList url="http://localhost:8000/members/?format=json" />,
    document.getElementById('member-list')
)