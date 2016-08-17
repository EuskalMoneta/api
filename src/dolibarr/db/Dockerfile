FROM mariadb:10.1

COPY dump-dolibarr-test.sql /docker-entrypoint-initdb.d/dump-dolibarr-test.sql

RUN chown mysql:mysql /docker-entrypoint-initdb.d/dump-dolibarr-test.sql