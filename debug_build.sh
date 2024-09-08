#!/bin/bash

name="debug/`pwd | sed -r 's/^.+\///' | sed -r 's/-/_/g'`"
hostname=`echo $name | awk -F'/' '{print $NF}'`
port=9800

if [ "$1" = '--build' ]; then
    docker build -f ./Dockerfile -t $name .
fi

docker-compose -f ./docker-compose.yaml up -d --remove-orphans

pwd=`pwd`
docker run --hostname=${hostname}:${port} -it --rm \
    -v "${pwd}:/app"  \
    -p "${port}:8000" \
    --network renthouse_net \
    $name bash

docker-compose -f ./docker-compose.yaml down
