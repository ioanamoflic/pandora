nvidia-smi
ipconfig /all
ifconfig -a
hostname -l | awk '{print $7}'
nvidia-smi
htop
ls
sudo apt-get update
sudo apt-get -y install podman
alias docker=podman
git clone https://github.com/alexandrupaler/zxreinforce_small.git
sudo usermod -a -G podman $USER
rm -rf zxreinforce_small/
sudo usermod -a -G docker $USER
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey |   sudo apt-key add -distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey |   sudo apt-key add -distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list
$distribution
echo $distribution
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
ls
mkdir optimization_projects
cd optimization_projects/
la
ls
git clone https://github.com/ioanamoflic/gvaeopt.git
git checkout max_test
cd gvaeopt/
git checkout max_test
cd 
cd optimization_projects/
ls
rm -rf gvaeopt
ls
git clone https://github.com/ioanamoflic/GnnRLOpt.git
ls
cd GnnRLOpt/
ls
git checkout max_test
ls
python3 venv -m venv
python3 -m venv venv
ls
source venv/bin/activate
pip install requirements.txt 
pip install -r requirements.txt 
gcc
git pull
pip install -r requirements.txt 
sudo apt-get install graphviz graphviz-dev
pip install -r requirements.txt 
apt install cargo
ls
apt install cargo
nano run_epyc.sh
ls
mkdir train_circuits
cd train_circuits/
la
ls
nano bvz_6_63
cd
cd optimization_projects/GnnRLOpt/
lz
ls
chmod 777 run_epyc.sh 
./run_epyc.sh
pip install numpy
nano requirements.txt 
./run_epyc.sh
nano run_epyc.sh 
echo $pythonpath
echo $PYTHONPATH
nano run_epyc.sh 
export PYTHONPATH=".:$PWD:$PWD/rl_related"
echo $PYTHONPATH
pip list
pip install requirements.txt 
pip install -r requirements.txt 
pip list
nano requirements.txt 
pip install -r requirements.txt 
pip list
./run_epyc.sh
ls
nano run_epyc.sh
export PYTHONPATH=".:$PWD:$PWD/rl_related"
echo $PYTHONPATH
nano run_epyc.sh

./run_epyc.sh
pip list
deactivate
nano run_epyc.sh 
python
python3
nano run_epyc.sh 
./run_epyc.sh
source venv/bin/activate
nano macos_requirements.txt 
cd ..
deactivate
cd GnnRLOpt/
diff macos_requirements.txt requirements.txt 
nano requirements.txt 
source venv/bin/activate
pip install -r macos_requirements.txt 
sudo apt-get install cargo
pip install -r macos_requirements.txt 
htop
cd optimization_projects/
ls
cd GnnRLOpt/
rm -rf venv/
python3.10 -m venv venv
sudo apt-get install python3.10-venv
python3.10 -m venv venv
source venv/bin/activate
python3
pip install -r macos_requirements.txt 
cat macos_requirements.txt 
sudo apt-get install graphviz graphviz-dev
sudo apt-get install python3.10-dev
pip install -r macos_requirements.txt 
cat run_epyc.sh 
deactivate
./run_epyc.sh 
cd ls
cd rl_related/
mkdir train_data
ps aux | grep rl_train
cd ..
./run_epyc.sh 
disown
htop
ls
cd optimization_projects/
ls
cd GnnRLOpt
ls
cd train_circuits/
ls
nano bvz_8_255
nano bvz_10_1023
ls
cat bvz_10_1023 
cat bvz_8_255 
ls
ps -aux|grep python
ps -aux|grep python| wc -l
ps -aux|grep rl_train.py| wc -l
podman --version
ls
cd optimization_projects/
ls
git clone https://github.com/ioanamoflic/pandora.git
git pull
podman compose up --build
podman-compose up --build
podman compose up --build
ls
cd pandora/
ls
git pull
podman compose up --build
podman --help
podman compose up build
docker-compose
podman compose
podman --help
ls
nano compose.yml 
podman compose
podman --v
podman -version
podman --version
nano Dockerfile 
podman pull
podman pull ubuntu/postgres
podman pull docker.io/library/ubuntu/postgres
docker pull ubuntu/postgres
sudo docker pull ubuntu/postgres
sudo $$
sudo sudo $$
sudo podman pull 
sudo podman pull docker.io/library/ubuntu/postgres
docker images ls
sudo docker images ls
docker container ls
sudo docker container ls
docker run ubuntu/postgres
sudo docker run ubuntu/postgres
sudo docker container ls
sudo docker images ls
sudo docker ps -a
docker save ubuntu/postgres | podman load
sudo docker save ubuntu/postgres | podman load
podman images ls
podman containers ls
podman container ls
ls
podman ps
podman ps -a
sudo podman container ls
sudo podman images ls
sudo podman images --root 
sudo podman images ls --root ~/.local/share/containers/storage/
sudo podman images --root ~/.local/share/containers/storage/
podman images --root ~/.local/share/containers/storage/
sudo podman images --root ~/.local/share/containers/storage/
sudo usermod -aG docker podman ioanamoflic
which docker
podman images --root ~/.local/share/containers/storage/
groups podman
groups ioanamoflic
sudo usermod -aG podman ioanamoflic
groupadd docker
sudo groupadd docker
sudo groupadd podman
sudo usermod -aG docker podman ioanamoflic
sudo usermod -a -G docker podman ioanamoflic
sudo usermod -a -G docker ioanamoflic
sudo usermod -a -G podman ioanamoflic
podman images --root ~/.local/share/containers/storage/
sudo chown -R ~/.local/share/containers
sudo chown -R ~/.local/share/containers ioanamoflic
sudo chown ioanamoflic -R ~/.local/share/containers
podman images --root ~/.local/share/containers/storage/
docker pull ubuntu/postgres
htop
sudo reboot
cd optimization_projects/pandora/
ls
docker pull ubuntu/postgres
docker save ubuntu/postgres | podman load
podman images ls
podman images
podman run --it bash
podman run localhost/ubuntu/postgres --interactive /bin/bash
podman run localhost/ubuntu/postgres --interactive /bin/bash -e POSTGRES_PASSWORD=1234 
podman 
podman --help
ls
cat compose.yml 
cp compose.yml compose_podman.yml
nano compose_podman.yml 
podman compose
podman-compose compose_podman.yml 
podman-compose
sudo apt-get install podman-compose
pip3 install podman-compose
podman-compose compose_podman.yml 
podman-compose 
podman-compose -f compose_podman.yml 
podman-compose build -f compose_podman.yml 
podman-compose -f compose_podman.yml build
nano compose_podman.yml 
podman-compose -f compose_podman.yml build
ls
nano compose_podman.yml 
podman-compose -f compose_podman.yml build
nano compose_podman.yml 
podman-compose -f compose_podman.yml build
nano compose_podman.yml 
podman-compose -f compose_podman.yml build
nano Dockerfile 
pip3 uninstall podman-compose
pip3 install podman-compose==1.1.0
podman-compose -f compose_podman.yml build
pip3 uninstall podman-compose
pip3 install podman-compose==1.0
pip3 install podman-compose==1.0.6
podman-compose -f compose_podman.yml build
ls
podman images
podman-compose -f compose_podman.yml up
ls
nano Dockerfile 
cat Dockerfile 
podman network create pandora_default
sudo apt update
sudo apt install podman
curl -O http://archive.ubuntu.com/ubuntu/pool/universe/g/golang-github-containernetworking-plugins/containernetworking-plugins_1.1.1+ds1-3build1_amd64.deb
dpkg -i containernetworking-plugins_1.1.1+ds1-3build1_amd64.deb
sudo dpkg -i containernetworking-plugins_1.1.1+ds1-3build1_amd64.deb
podman-compose -f compose_podman.yml up
podman images
podman-compose -f compose_podman.yml --name pandora1609 build
podman-compose
podman-compose -f compose_podman.yml build
podman /localhost/ubuntu/postgres --interactive /bin/bash run
podman run /localhost/ubuntu/postgres --interactive /bin/bash
podman
podman --help
podman run /localhost/ubuntu/postgres --interactive /bin/bash
podman run /localhost/ubuntu/postgres
podman run localhost/ubuntu/postgres
podman images
podman ps -a
podman rm vigilant_joliot 
podman ps -a
podman run pandora_db_1
pandora rm pandora_res.png 
podman rm pandora_db_1 
podman run localhost/ubuntu/postgres --interactive /bin/bash
podman-compose -f compose_podman.yml up
podman ps -a
podman rm vigilant_clarke 
podman rm pedantic_brattain 
ls
podman ps -a
docker ps -a
docker rm nice_ritchie
podman images
podman ps -a
podman exec -it pandora_db_1 sh
