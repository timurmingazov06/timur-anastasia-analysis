#!/bin/bash

# Проверяем, передан ли путь
if [ -z "$1" ]; then
  echo "Usage: $0 /path/to/app"
  exit 1
fi

# Получаем путь к .app
APP_PATH="$1"

# Проверяем, существует ли папка Contents/MacOS
MACOS_PATH="$APP_PATH/Contents/MacOS"
if [ ! -d "$MACOS_PATH" ]; then
  echo "Error: $MACOS_PATH does not exist."
  exit 1
fi

# Делаем все файлы внутри Contents/MacOS исполняемыми
chmod +x "$MACOS_PATH"/*

echo "Permissions updated for files in $MACOS_PATH"
