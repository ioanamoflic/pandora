Build the container on 22.04 Ubuntu server
```
docker pull ubuntu/postgres
docker save ubuntu/postgres | podman load

pip3 install podman-compose==1.0.6
curl -O http://archive.ubuntu.com/ubuntu/pool/universe/g/golang-github-containernetworking-plugins/containernetworking-plugins_1.1.1+ds1-3build1_amd64.deb
sudo dpkg -i containernetworking-plugins_1.1.1+ds1-3build1_amd64.deb
```

Start the container (from scratch) in the background
```
podman-compose -f compose_podman.yml build
podman-compose -f compose_podman.yml up -d
```

Resume container 
```
podman start pandora_db_1
```

Connect to the container
```
podman exec -it pandora_db_1 sh
```
