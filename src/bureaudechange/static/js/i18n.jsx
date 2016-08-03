import i18next from 'i18next'
import XHR from 'i18next-xhr-backend'
// import Cache from 'i18next-localstorage-cache'
// import sprintf from 'i18next-sprintf-postprocessor'
// import LngDetector from 'i18next-browser-languagedetector'

// function loadLocales(url, options, callback, data) {
//   try {
//     console.log("url toto: " + url)
//     let waitForLocale = require('bundle!' + url);
//     waitForLocale((locale) => {
//       callback(locale, {status: '200'});
//     })
//   } catch (e) {
//     callback(null, {status: '404'});
//   }
// }

const i18nextOptions = {
    debug: true,
    whitelist: ['fr', 'eu'],
    fallbackLng: 'fr',
    // XHR config
    backend: {
        // path where resources get loaded from
        loadPath: '/static/locales/{{lng}}/{{ns}}.json',

        // your backend server supports multiloading
        // /locales/resources.json?lng=de+en&ns=ns1+ns2
        allowMultiLoading: false,

        // parse data after it has been fetched
        parse: (data) => data,

        // allow cross domain requests
        crossDomain: false
    },
    // // Cache config
    // cache: {
    //     // turn on or off
    //     enabled: false,

    //     // prefix for stored languages
    //     prefix: 'i18next_res_',

    //     // expiration
    //     expirationTime: 7*24*60*60*1000
    // },
    // detection: {
    //     // order and from where user language should be detected
    //     order: ['navigator', 'htmlTag', 'querystring', 'cookie', 'localStorage'],

    //     // keys or params to lookup language from
    //     lookupQuerystring: 'lng',
    //     lookupCookie: 'i18next',
    //     lookupLocalStorage: 'i18nextLng',

    //     // cache user language on
    //     caches: ['localStorage', 'cookie']

    //     // optional expire and domain for set cookie
    //     // cookieMinutes: 10,
    //     // cookieDomain: 'myDomain',
    // }
}

i18next
    .use(XHR)
    // .use(Cache)
    // .use(LngDetector)
    // .use(sprintf)
    .init(i18nextOptions,
            (err, t) => {
            // initialized and ready to go!
            const hw = i18next.t('key')
            console.log('i18n INIT OK')
            console.log(hw)
    })

module.exports = {
    i18n: i18next
}