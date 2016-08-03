// require our dependencies
var webpack = require('webpack')
var path = require('path')


module.exports = {
    // the base directory (absolute path) for resolving the entry option
    context: __dirname,

    // the entry point we created earlier. Note that './' means
    // your current directory. You don't have to specify the extension  now,
    // because you will specify extensions later in the `resolve` section

    entry: {
        Base : './static/js/base', // Your global app's entry point
        MemberList : './static/js/member-list',
        MemberAdd : './static/js/member-add'
    },

    output: {
        // where you want your compiled bundle to be stored
        path: '/assets/bundles/',
        // naming convention webpack should use for your files
        filename: 'js/[name].js',
    },

    plugins: [
        // prints compilation errors in the console browser
        new webpack.NoErrorsPlugin(),
        // makes our dependencies available in every module
        new webpack.ProvidePlugin({
            Promise: 'imports?this=>global!exports?global.Promise!es6-promise',
            fetch: 'imports?this=>global!exports?global.fetch!whatwg-fetch',
            Raven: 'raven-js',
            React: 'react',
            ReactDOM: 'react-dom',
            ReactToastr: 'react-toastr',
            Formsy: 'formsy-react',
            FRC: 'formsy-react-components',
            moment: 'moment'
        }),
    ],

    url: {
        dataUrlLimit: 1024 // 1 kB
    },
    module: {
        loaders: [
            // a regexp that tells webpack use the following loaders on all
            // .js and .jsx files
            {
                test: /\.jsx?$/,
                // we definitely don't want babel to transpile all the files in
                // node_modules. That would take a long time.
                exclude: /node_modules/,
                // use the babel loader
                loader: 'babel'
            },
            // Classic CSS + SASS preprocessor
            {
                test: /\.css$/,
                exclude: /\.useable\.css$/,
                loaders: ['style', 'css']
            },
            {
                test: /\.useable\.css$/,
                loaders: ['style/useable', 'css']
            },
            {
                test: /\.scss$/,
                loaders: ["style", "css?sourceMap", "sass?sourceMap"]
            },
            {
                test: /\.json/,
                loader: 'json-loader'
            },
            // We want to use bootstrap
            // Bootstrap is based on webfonts / svg and other cool things
            // We need webpack to handle those for us
            {
                test: /\.svg/,
                loader: 'svg-url-loader'
            },
            {
                test: /\.woff(2)?(\?v=[0-9]\.[0-9]\.[0-9])?$/,
                loader: "url-loader?limit=10000&mimetype=application/font-woff"
            },
            {
                test: /\.(ttf|eot|svg)(\?v=[0-9]\.[0-9]\.[0-9])?$/,
                loader: "file-loader"
            }
        ]
    },

    resolve: {
        root: path.resolve(__dirname),

        alias: {
            Utils: 'static/js/utils',
            i18n: 'static/js/i18n'
        },

      // tells webpack where to look for modules
        modulesDirectories: ['node_modules'],
        // extensions that should be used to resolve modules
        extensions: ['', '.js', '.jsx']
    }
}