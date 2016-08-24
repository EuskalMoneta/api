import {
    NavbarTitle
} from 'Utils'

class Manager extends React.Component {
    constructor(props) {
        super(props)
    }

    render() {
        return (
            <div className="col-md-10">
                <StockBillets />
                <CaisseEuro />
                <CaisseEusko />
                <RetourEusko />
            </div>
        )
    }
}

class StockBillets extends React.Component {
    render() {
        return (
            <div className="panel panel-info">
                <div className="panel-heading">
                    <h3 className="panel-title">{__("Stock de billets")}</h3>
                </div>
                <div className="panel-body">
                    <div className="row">
                        <div className="col-md-8 col-sm-4">
                            <label className="control-label col-md-3">{__("Solde")} :</label>&nbsp;
                            <span className="col-md-5">512 eusko</span>
                        </div>
                        <div className="col-md-4">
                            <a className="btn btn-default">{__("Historique")}</a>
                        </div>
                    </div>
                    <div className="row margin-top">
                        <div className="col-md-offset-2 col-md-2 col-sm-4">
                            <a className="btn btn-info">{__("Entrée")}</a>
                        </div>
                        <div className="col-md-offset-2 col-md-2 col-sm-4">
                            <a className="btn btn-default">{__("Sortie")}</a>
                        </div>
                    </div>
                </div>
            </div>
        )
    }
}

class CaisseEuro extends React.Component {
    render() {
        return (
            <div className="panel panel-warning">
                <div className="panel-heading">
                    <h3 className="panel-title">{__("Caisse euros")}</h3>
                </div>
                <div className="panel-body">
                    <div className="row">
                        <div className="col-md-8 col-sm-4">
                            <label className="control-label col-md-3">{__("Solde")} :</label>&nbsp;
                            <span className="col-md-5">1232 eusko</span>
                        </div>
                        <div className="col-md-4">
                            <a className="btn btn-default">{__("Historique")}</a>
                        </div>
                    </div>
                     <div className="row">
                        <div className="col-md-8 col-sm-4">
                            <label className="control-label col-md-3">{__("Espèces")} :</label>&nbsp;
                            <span className="col-md-5">742 €</span>
                        </div>
                    </div>
                    <div className="row margin-top">
                        <div className="col-md-8 col-sm-4">
                            <label className="control-label col-md-3">{__("Chèques")} :</label>&nbsp;
                            <span className="col-md-5">490 €</span>
                        </div>
                    </div>
                    <div className="row margin-top">
                        <div className="col-md-offset-2 col-md-2 col-sm-4">
                            <a className="btn btn-warning">{__("Dépôt en banque")}</a>
                        </div>
                        <div className="col-md-offset-2 col-md-2 col-sm-4">
                            <a className="btn btn-danger btn-danger-inverse">{__("Remise d'espèces")}</a>
                        </div>
                    </div>
                </div>
            </div>
        )
    }
}

class CaisseEusko extends React.Component {
    render() {
        return (
            <div className="panel panel-success">
                <div className="panel-heading">
                    <h3 className="panel-title">{__("Caisse eusko")}</h3>
                </div>
                <div className="panel-body">
                    <div className="row">
                        <div className="col-md-8 col-sm-4">
                            <label className="control-label col-md-3">{__("Solde")} :</label>&nbsp;
                            <span className="col-md-5">13 eusko</span>
                        </div>
                        <div className="col-md-4">
                            <a className="btn btn-default">{__("Historique")}</a>
                        </div>
                    </div>
                    <div className="row margin-top">
                        <div className="col-md-offset-2 col-md-2 col-sm-4">
                            <a className="btn btn-success">{__("Sortie")}</a>
                        </div>
                    </div>
                </div>
            </div>
        )
    }
}

class RetourEusko extends React.Component {
    render() {
        return (
            <div className="panel panel-primary">
                <div className="panel-heading">
                    <h3 className="panel-title">{__("Retour eusko")}</h3>
                </div>
                <div className="panel-body">
                    <div className="row">
                        <div className="col-md-8 col-sm-4">
                            <label className="control-label col-md-3">{__("Solde")} :</label>&nbsp;
                            <span className="col-md-5">128 eusko</span>
                        </div>
                        <div className="col-md-4">
                            <a className="btn btn-default">{__("Historique")}</a>
                        </div>
                    </div>
                    <div className="row margin-top">
                        <div className="col-md-offset-2 col-md-2 col-sm-4">
                            <a className="btn btn-primary">{__("Sortie")}</a>
                        </div>
                    </div>
                </div>
            </div>
        )
    }
}

ReactDOM.render(
    <Manager />,
    document.getElementById('manager')
)

ReactDOM.render(
    <NavbarTitle title={__("Gestion")} />,
    document.getElementById('navbar-title')
)