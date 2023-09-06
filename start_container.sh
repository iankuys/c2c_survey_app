#!/bin/bash
app="c2c-retention-dce"
port=8080

echo "Stopping ${app}"
docker stop ${app}

echo "Removing ${app}"
docker rm ${app}

echo "Building ${app}"
docker build -t ${app} .

echo "Running ${app}"
docker run -d \
  --restart unless-stopped \
  -p ${port}:${port} \
  --name=${app} \
  -v $PWD:/app ${app}
