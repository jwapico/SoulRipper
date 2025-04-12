#!/bin/bash

container=$(docker ps -a --filter "name=soulripper" -q)

if [ -n "$container" ]; then
    echo "Container exists. Bringing it down and removing volumes..."
    docker compose down --volumes --remove-orphans
else
    echo "No container found. Proceeding with build and start..."
fi

echo "Building container(s)..."
docker compose build

echo "Starting container(s)..."
docker compose up -d

echo "Entering 'soulripper' container shell..."
docker exec -it soulripper bash
