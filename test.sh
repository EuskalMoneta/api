#!/bin/bash
# Test Euskal Moneta API

COMPOSE_PROJECT_NAME='eusko_api_test'  # Avoid conflicts with non-test machines.
export COMPOSE_PROJECT_NAME

docker-compose rm -f

set -e

function run {
    # test -d etc || cp -r etc_ci etc  # Provision local configuration.
    docker-compose build

    echo "Testing api..."
    docker-compose up -d api
    echo "Waiting for api to startup..."
    sleep 30
    docker-compose run --rm -u root api bash -c "py.test"
}

function teardown {
    docker-compose stop
    docker-compose rm -f
}

( run && teardown ) || ( teardown && exit 1 )