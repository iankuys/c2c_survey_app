#!/bin/bash
app="c2c-dcv"
echo "Stopping ${app}"
docker stop ${app}

echo "Removing ${app}"
docker rm ${app}

echo "Building ${app}"
docker build -t ${app} .

echo "Running ${app}"
docker run -d \
  --restart unless-stopped \
  -p 8080:8080 \
  --name=${app} \
  -v $PWD:/app ${app}
