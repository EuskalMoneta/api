FROM python:3.4

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
	--no-install-recommends && rm -rf /var/lib/apt/lists/*

ENTRYPOINT /cyclos/setup_cyclos.sh

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
