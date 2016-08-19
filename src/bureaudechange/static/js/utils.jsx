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
var getCSRFToken = document.getElementById('csrfmiddlewaretoken').value
var getAPIBaseURL = document.getElementById('apibaseurl').value

module.exports = {
    checkStatus: checkStatus,
    parseJSON: parseJSON,
    getCurrentLang: getCurrentLang,
    getCSRFToken: getCSRFToken,
    getAPIBaseURL: getAPIBaseURL
}