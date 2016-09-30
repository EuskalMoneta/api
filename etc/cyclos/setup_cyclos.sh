#!/bin/bash

# This is how I launch this script (in dev):
# docker-compose exec api bash /cyclos/setup_cyclos.sh

# This cd will do this: cd /cyclos/
cd "${0%/*}"

rm -f cyclos_constants.yml

# Base64('admin:admin') = YWRtaW46YWRtaW4=
python setup.py http://cyclos-app:8080/ YWRtaW46YWRtaW4=
python init_test_data.py http://cyclos-app:8080/ YWRtaW46YWRtaW4=