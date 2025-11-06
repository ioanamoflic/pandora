IMG_DIR=apptainer/images
APP_NAME=pandora


.PHONY: all build clean update test apptainer_build apptainer_base

all: build

build: apptainer_build
	pip install -e .

clean:
	pip uninstall -y ${APP_NAME}

update:
	git pull origin
	${MAKE} build

test:
	pytest

apptainer_build: apptainer_base
	cd apptainer;
		mkdir -p "${IMG_DIR}"; \
		singularity build "${IMG_DIR}/pandora.sif" docker-daemon://local/${APP_NAME}:latest

apptainer_base:
	cd apptainer; \
		mkdir -p "${IMG_DIR}"; \
		docker build -t local/${APP_NAME}:latest .

