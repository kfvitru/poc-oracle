FROM python:3.12-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY main.py .
COPY test_oci_direct.py .
COPY test_auth.py .
COPY *.sh ./

# Tornar scripts executáveis
RUN chmod +x *.sh

# Variável de ambiente para Python não criar __pycache__
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Comando padrão
CMD ["python", "main.py"]
