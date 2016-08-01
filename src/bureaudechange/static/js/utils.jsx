var checkStatus = function (response) {
    if (response.status >= 200 && response.status < 300) {
        return response
    } else {
        var error = new Error(response.statusText)
        error.response = response
        throw error
    }
}

var parseJSON = function (response) {
  return response.json()
}

module.exports = {
    checkStatus: checkStatus,
    parseJSON: parseJSON
}