var React = require('react')
var ReactDOM = require('react-dom')

var MemberList = require('./member-list').memberlist

ReactDOM.render(
    <MemberList url="http://localhost:8000/members/?format=json" />,
    document.getElementById('member-list')
)