FROM python:3.8-slim

# Variables d'environnement pour Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Création des répertoires
RUN mkdir -p /usr/src/app /cyclos /dolibarr
WORKDIR /usr/src/app

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    gettext \
    default-mysql-client \
    default-libmysqlclient-dev \
    postgresql-client \
    libpq-dev \
    sqlite3 \
    libfreetype6-dev \
    wget \
    xvfb \
    curl \
    wkhtmltopdf \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copie et installation des dépendances Python
COPY src/api/requirements.txt /usr/src/app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copie du code de l'application
COPY src/api /usr/src/app
COPY etc/cyclos /cyclos
COPY etc/dolibarr /dolibarr

# Rendre le script exécutable
RUN chmod +x /cyclos/setup_cyclos.sh

EXPOSE 8000

ENTRYPOINT ["/cyclos/setup_cyclos.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
