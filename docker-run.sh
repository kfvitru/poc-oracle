#!/bin/bash

# Script para executar o projeto usando Docker

# Verificar se o .env existe
if [ ! -f ".env" ]; then
    echo "❌ Arquivo .env não encontrado!"
    echo "📝 Crie o arquivo .env com suas credenciais:"
    echo "   nano .env"
    exit 1
fi

# Verificar se docker-compose está instalado
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    echo "❌ Docker não está instalado!"
    echo "📦 Instale o Docker primeiro: https://docs.docker.com/get-docker/"
    exit 1
fi

# Usar docker-compose ou docker compose (versão mais nova)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

echo "🐳 Construindo a imagem Docker..."
$DOCKER_COMPOSE build

echo ""
echo "🚀 Iniciando o assistente de atendimento acadêmico no Docker..."
echo "📝 Os logs serão exibidos abaixo. Use Ctrl+C para parar."
echo ""

# Executar o container
$DOCKER_COMPOSE run --rm poc-oracle
