#!/bin/bash

# Wczytanie zmiennych z pliku .env
export $(grep -v '^#' .env | xargs)

# Nazwa obrazu i kontenera
IMAGE_NAME=sensor_service
CONTAINER_NAME=sensor_service

# Budowanie obrazu Docker
docker build -t ${IMAGE_NAME} .

# Sprawdzenie, czy kontener już istnieje
if [ "$(docker ps -aq -f name=${CONTAINER_NAME})" ]; then
    # Jeśli kontener działa, zatrzymaj go i usuń
    docker stop ${CONTAINER_NAME}
    docker rm ${CONTAINER_NAME}
fi

# Uruchomienie nowego kontenera
docker run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:5000 \
    ${IMAGE_NAME}
