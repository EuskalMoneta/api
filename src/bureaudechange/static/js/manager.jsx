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
                            <label className="control-label col-md-3">Solde :</label>&nbsp;
                            <span className="col-md-5">512 eusko</span>
                        </div>
                        <div className="col-md-4">
                            <a className="btn btn-default">{__("Historique")}</a>
                        </div>
                    </div>
                    <div className="row">
                        <div className="col-md-offset-2 col-md-2 col-sm-4">
                            <a className="btn btn-primary">{__("Entrée")}</a>
                        </div>
                        <div className="col-md-offset-2 col-md-2 col-sm-4">
                            <a className="btn btn-default">{__("Sortie")}</a>
                        </div>
                    </div>
                    <div className="row">
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