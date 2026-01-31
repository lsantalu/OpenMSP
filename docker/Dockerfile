# Usa un'immagine base ufficiale Python leggera
FROM python:3.10-slim

# Imposta variabili d'ambiente (Sintassi corretta con =)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Imposta la directory di lavoro
WORKDIR /app

# Installa dipendenze di sistema E l'utility dos2unix
RUN apt-get update && apt-get install -y \
    build-essential \
    python3.12-dev \
    libldap2-dev \
    libsasl2-dev \ 
    libpq-dev \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Copia e installa le dipendenze Python
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia lo script di entrypoint
COPY docker/entrypoint.sh /app/

# FONDAMENTALE: Converte il file da formato Windows a Linux e lo rende eseguibile
RUN dos2unix /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Copia il resto del codice sorgente
COPY . /app/

# Esponi la porta
EXPOSE 8000

# Definisci l'entrypoint
ENTRYPOINT ["bash", "/app/entrypoint.sh"]