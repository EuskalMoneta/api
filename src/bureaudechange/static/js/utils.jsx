var checkStatus = (response) => {
    if (response.status >= 200 && response.status < 300) {
        return response
    } else {
        var error = new Error(response.statusText)
        error.response = response
        throw error
    }
}

var parseJSON = (response) => {
    return response.json()
}

var getCurrentLang = document.documentElement.lang
var getCSRFToken = window.config.getCSRFToken
var getAPIBaseURL = window.config.getAPIBaseURL

var Flag = React.createClass({

    handleClick() {
        var data = {language: this.props.lang}

        fetch('/i18n/setlang_custom/',
        {
            body: data,
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': getCSRFToken,
                'Accept-Language': this.props.lang
            }
        })
        .then(response => {
            // Reload the current page, without using the cache
            window.location.reload(true)
            console.log('i18n lang change from ' + getCurrentLang  + ' to:' + this.props.lang)
        })
        .catch(err => {
            // Error during request, or parsing NOK :(
            console.log('/i18n/setlang_custom/' + this.props.lang, err)
        })
    },

    render() {
        // We want to hide the flag showing the current lang
        if (this.props.lang != getCurrentLang) {
            return (
                    <li>
                        <a className={"lang-select " + this.props.lang}
                           onClick={this.handleClick}>
                            <img className={"lang-select-flag-" + this.props.lang}
                                 alt={this.props.langname}
                                 src={"/static/img/" + this.props.lang + ".gif"}
                                 />
                        </a>
                    </li>
            )
        }
        else { return null }
    }
})

class Flags extends React.Component {
    constructor(props) {
        super(props)
    }

    render() {
        return (
            <ul className="nav navbar-nav pull-right">
                <Flag lang="eu" langname="Euskara"/>
                <Flag lang="fr" langname="Français"/>
            </ul>
        )
    }
}

class NavbarTitle extends React.Component {
    render = () => {
        if (this.props.title) {
            return <a className="navbar-brand">{this.props.title}</a>
        }
        else {
            return <a className="navbar-brand">Euskal Moneta</a>
        }
    }
}

class SidebarNav extends React.Component {
    render = () => {
        return (
            <ul className="sidebar-nav">
                {this.props.objects.map((item) => {
                    return (
                        <li key={item.id}>
                            <a href={item.href}>{item.label}</a>
                        </li>
                    )
                })}
            </ul>
        )
    }
}

module.exports = {
    checkStatus: checkStatus,
    parseJSON: parseJSON,
    getCurrentLang: getCurrentLang,
    getCSRFToken: getCSRFToken,
    getAPIBaseURL: getAPIBaseURL,
    NavbarTitle: NavbarTitle,
    SidebarNav: SidebarNav,
    Flags: Flags,
    Flag: Flag
}