#!/bin/bash

# WSL用 Redmine起動スクリプト
# Windows PowerShellから実行: wsl ./start-redmine.sh

echo "Starting Redmine development environment..."

# プロジェクトディレクトリに移動
cd "$(dirname "$0")"

# Docker Composeでコンテナを起動
docker-compose up -d

echo "Waiting for services to be ready..."
sleep 10

# コンテナの状態を確認
docker-compose ps

echo ""
echo "Redmine is starting up..."
echo "Please wait 1-2 minutes for initial setup, then access:"
echo "  URL: http://localhost:3000"
echo "  Username: admin"
echo "  Password: admin"
echo ""
echo "To check logs: docker-compose logs -f"
echo "To stop: docker-compose down"
