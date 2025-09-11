FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for WeasyPrint and wkhtmltopdf
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    wget \
    xz-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb \
    && dpkg -i wkhtmltox_0.12.6-1.buster_amd64.deb || true \
    && apt-get update && apt-get -f -y install \
    && rm wkhtmltox_0.12.6-1.buster_amd64.deb

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Hardcode port to 8080 - this is what Railway expects
EXPOSE 8080

# Use explicit command - no variable substitution
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "wsgi:app"]
