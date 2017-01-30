FROM python:3.5

RUN mkdir -p /usr/src/app /cyclos
WORKDIR /usr/src/app

COPY src/api/requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY src/api /usr/src/app

COPY etc/cyclos /cyclos
COPY etc/dolibarr /dolibarr

RUN apt-get update && apt-get install -y \
        gcc \
        gettext \
        mysql-client libmysqlclient-dev \
        postgresql-client libpq-dev \
        sqlite3 \
    --no-install-recommends 

# libjpeg, needed for Pillow ; xvfb for wkhtmltopdf
RUN apt-get install -y libfreetype6-dev wget xvfb && \
    cd /tmp && \
    wget https://bitbucket.org/wkhtmltopdf/wkhtmltopdf/downloads/wkhtmltox-0.13.0-alpha-7b36694_linux-jessie-amd64.deb && \
    dpkg --force-depends -i /tmp/wkhtmltox-0.13.0-alpha-7b36694_linux-jessie-amd64.deb && \
    apt-get install -fy && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/cyclos/setup_cyclos.sh"]

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]