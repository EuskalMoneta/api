var React = require('react')

const MemberList = React.createClass({
    getInitialState: function() {
        return {data: []};
    },
    componentDidMount: function() {
        $.ajax({
            type: "get",
            // URL que l'on va requeter
            url: this.props.url,
            // Données à passer pour faire une recherche
            dataType: 'json',
            // Fonction exécutée en cas de réussite de la requete,
            // la var data étant ce que l'on a récupéré comme résultat
            success: function(data)
            {
                this.setState({data: data.results});
            }.bind(this),
            error: function(xhr, status, err) {
                console.error(this.props.url, status, err.toString());
            }.bind(this),
        });
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

module.exports = {
    memberlist: MemberList,
    member: Member
}
