FROM php:5.6-apache

RUN apt-get update && apt-get install -y libpng12-dev libjpeg-dev git \
    && rm -rf /var/lib/apt/lists/* \
    && docker-php-ext-configure gd --with-png-dir=/usr --with-jpeg-dir=/usr \
    && docker-php-ext-install gd

RUN git clone https://github.com/EuskalMoneta/dolibarr.git /dolibarr

RUN docker-php-ext-install mysqli

COPY ./conf/date-timezone.ini ./conf/memory_limit.ini /usr/local/etc/php/conf.d/

RUN cp -r /dolibarr/htdocs/* /var/www/html/

COPY ./conf/conf.php /var/www/html/conf/

RUN chown -hR www-data:www-data /var/www/html \
    && mkdir /var/www/documents \
        && chown -hR www-data:www-data /var/www/documents

EXPOSE 80
