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

var storeToken = (data) => {
    // Save data to sessionStorage
    sessionStorage.setItem('api-token-auth', data.token)
    return data.token
}

var getToken = () => {
    // Get saved data from sessionStorage
    return sessionStorage.getItem('api-token-auth')
}

var fetchCustom = (url, method, promise, token, data, promiseError) => {
    var payload = {
        method: method,
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Token ' + token
        }
    }

    if (method.toLowerCase() == 'post') {
        payload.body = JSON.stringify(data)
    }

    if (!promiseError) {
        var promiseError = (err) => {
            // Error during request, or parsing NOK :(
            console.log(url, method, promise, token, data, promiseError, err)
        }
    }

    fetch(url, payload)
    .then(checkStatus)
    .then(parseJSON)
    .then(promise)
    .catch(promiseError)
}

var fetchAuth = (url, method, promise, data=null, promiseError=null) => {
    var token = getToken()
    if (token) {
        console.log("We have a token")
        // Cas 2: On a le token
        fetchCustom(url, method, promise, token, data, promiseError)
    }
    else {
        console.log("We need a token")
        // Cas 1: On a pas le token
        fetch(getAPIBaseURL + 'api-token-auth/',
        {
            method: 'post',
            body: JSON.stringify({'username': 'admin', 'password': 'admin'}),
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        })
        .then(checkStatus)
        .then(parseJSON)
        .then(storeToken)
        .then((token) => {
            fetchCustom(url, method, promise, token, data, promiseError)
        })
        .catch(err => {
            // Error during request, or parsing NOK :(
            console.log(url, method, promise, data, promiseError, err)
        })
    }
}

var isMemberIdEusko = (values, value) =>
{
    if (!value) {
        return false;
    }

    if ((value.startsWith("E", 0) || value.startsWith("Z", 0)) && value.length === 6) {
        return true;
    }
    else {
        return false;
    }
}

var titleCase = (str) => {
  if ((str===null) || (str===''))
       return false;
  else
   str = str.toString();

 return str.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
}

var getCurrentLang = document.documentElement.lang
var getCSRFToken = window.config.getCSRFToken
var getAPIBaseURL = window.config.getAPIBaseURL

var Flag = React.createClass({
    render() {
        // We want to hide the flag showing the current lang
        if (this.props.lang != getCurrentLang) {
            return (
                    <li>
                        <a className={"lang-select " + this.props.lang}
                           href={"/i18n/setlang_custom/?lang=" + this.props.lang}>
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

class SelectizeUtils {
    // generic callback for all selectize objects
    static selectizeCreateFromSearch(options, search) {
        // Pretty much self explanatory:
        // this function is called when we start typing inside the select
        if (search)
        {
            if (search.length == 0 || (options.map(function(option)
            {
                return option.label;
            })).indexOf(search) > -1)
                return null;
            else
                return {label: search, value: search};
        }
        else
            return null;
    }

    static selectizeRenderOption (item) {
        // This is how the list itself is displayed
        return  <div className="simple-option" style={{display: "flex", alignItems: "center"}}>
                    <div className="memberaddform" style={{marginLeft: 10}}>
                        {item.label}
                    </div>
                </div>
    }

    static selectizeNewRenderOption (item) {
        // This is how the list itself is displayed
        return  <div className="simple-option" style={{display: "flex", alignItems: "center"}}>
                    <div className="memberaddform" style={{marginLeft: 10}}>
                        {!!item.newOption ? __("Ajouter") + " " + item.label + " ..." : item.label}
                    </div>
                </div>
    }

    static selectizeRenderValue (item) {
        // When we select a value, this is how we display it
        return  <div className="simple-value">
                    <span className="memberaddform" style={{marginLeft: 10, verticalAlign: "middle"}}>{item.label}</span>
                </div>
    }

    static selectizeNoResultsFound () {
        return  <div className="no-results-found" style={{fontSize: 15}}>
                    {__("Pas de résultat")}
                </div>
    }
}


module.exports = {
    checkStatus: checkStatus,
    parseJSON: parseJSON,
    fetchAuth: fetchAuth,
    isMemberIdEusko: isMemberIdEusko,
    titleCase: titleCase,
    getCurrentLang: getCurrentLang,
    getCSRFToken: getCSRFToken,
    getAPIBaseURL: getAPIBaseURL,
    NavbarTitle: NavbarTitle,
    SidebarNav: SidebarNav,
    Flags: Flags,
    Flag: Flag,
    SelectizeUtils: SelectizeUtils
}