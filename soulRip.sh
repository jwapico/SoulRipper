#!/bin/bash

running=$(docker ps --filter "name=soulripper" -q)

if [ -n "$running" ]; then
    echo "Container is running. Bringing it down and removing volumes..."
    docker-compose down --volumes
else
    echo "No running container found. Proceeding with build and start..."
fi

echo "Building container(s)..."
docker-compose build

echo "Starting container(s)..."
docker-compose up -d

echo "Entering 'soulripper' container shell..."
docker exec -it soulripper bash