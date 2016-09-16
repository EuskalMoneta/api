#!/bin/bash

cd "${0%/*}"

rm -f cyclos_constants.yml

python setup.py http://cyclos-app:8080/ YWRtaW46YWRtaW4=
python init_static_data.py http://cyclos-app:8080/ YWRtaW46YWRtaW4=