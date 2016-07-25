import Formsy from 'formsy-react';

import {EuskoInput, EuskoButton} from './forms-eusko.jsx';

const MemberAddForm = React.createClass({
    getInitialState: function() {
      return {
        canSubmit: false
      }
    },
    enableButton: function() {
      this.setState({
        canSubmit: true
      });
    },
    disableButton: function() {
      this.setState({
        canSubmit: false
      });
    },
    submit: function(model) {
        console.log(model);

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
      return (
        <Formsy.Form onValidSubmit={this.submit} onValid={this.enableButton} onInvalid={this.disableButton}>
          <EuskoInput name="email" validations="isEmail" validationError="This is not a valid email" required/>
          <button type="submit" disabled={!this.state.canSubmit}>Submit</button>
        </Formsy.Form>
      );
    }
});
// <EuskoButton disabled={!this.state.canSubmit}>Ajouter un adhérent</EuskoButton>

ReactDOM.render(
    <MemberAddForm url="http://localhost:8000/members?format=json" />,
    document.getElementById('member-add')
);