// require our dependencies
var webpack = require('webpack')

module.exports = {
    // the base directory (absolute path) for resolving the entry option
    context: __dirname,

    // the entry point we created earlier. Note that './' means
    // your current directory. You don't have to specify the extension  now,
    // because you will specify extensions later in the `resolve` section

    entry: {Base : './static/js/base', // Your global app's entry point
            MemberList : './static/js/member-list',
            MemberAdd : './static/js/member-add'
            },

    output: {
        // where you want your compiled bundle to be stored
        path: './static/js/bundles/',
        // naming convention webpack should use for your files
        filename: '[name].js',
    },

    plugins: [
        // prints compilation errors in the console browser
        new webpack.NoErrorsPlugin(),
        // makes our dependencies available in every module
        new webpack.ProvidePlugin({
            $: 'jquery',
            jQuery: 'jquery',
            'window.jQuery': 'jquery',
            React: 'react',
            ReactDOM: 'react-dom',
            Formsy: 'formsy-react',
            FRC: 'formsy-react-components',
            moment: 'moment'
        })
    ],

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
            { test: /\.css$/, exclude: /\.useable\.css$/, loader: "style!css" },
            { test: /\.useable\.css$/, loader: "style/useable!css" }
        ]
    },

    resolve: {
        // tells webpack where to look for modules
        modulesDirectories: ['node_modules'],
        // extensions that should be used to resolve modules
        extensions: ['', '.js', '.jsx']
    }
}