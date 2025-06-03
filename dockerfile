# Stage 1: Builder -> Cargamos la imagen base de Python 3.11 slim (esto se obtiene de Docker Hub)
FROM python:3.11-slim AS builder

# Set environment variables to avoid writing .pyc files and to ensure output is sent directly to the terminal
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# se crea un nuevo folder de trabajo dentro del contenedor
WORKDIR /app

# L
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Stage 2: Runtime -> una vez que se han instalado las dependencias, se crea una nueva imagen para la ejecución
FROM python:3.11-slim

# configuramos nuestro host y puerto
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 

# La imagen de runtime trabaja con el mismo path de trabajo que el builder
WORKDIR /app

# copiamos las depedencias de python y el código fuente desde el builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /app /app

# Create non-root user and set permissions
RUN useradd --create-home fastapi

USER fastapi

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Este comado inicia la aplicación FastAPI usando Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]