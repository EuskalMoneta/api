// Load here global React objects like a navbar, i18n flags clicks, etc...
// We can load our Sass stylesheets which will be included in the bundle using Webpack,
// thus we can also setup JavaScript things ... all of those will be used everywhere in our app

// Load our CSS stylesheets
require('../css/bootstrap.min.css')
require('../css/animate.min.css')
require('../css/toastr.min.css')
require('../css/style.css')

// Load our base Sass stylesheet
require('../scss/style.scss')

// Setup momentjs to be french :)
moment.locale('fr')

// Setup raven (Sentry client)
Raven.config('http://02c622eee5004e9fa9b661395e6ca409@localhost:8081/3').install()
