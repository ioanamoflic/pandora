#!/usr/bin/env bash
set -eu
IMAGES_DIR="images"

# the name of the docker image to start from
BASE_IMAGE="postgres:latest"

# the name of the project
APP_NAME="pandora"

base() {
    mkdir -p "$IMAGES_DIR"
    #apptainer build "$IMAGES_DIR/$BASE_IMAGE.sif" "docker://$BASE_IMAGE"
    docker build -t local/$APP_NAME:latest .
}

build() {
    mkdir -p "$IMAGES_DIR"
    singularity build images/pandora.sif docker-daemon://local/$APP_NAME:latest
    #apptainer build --sandbox "$IMAGES_DIR/$APP_NAME.sif" project.apptainer
}

run() {
    apptainer run "$IMAGES_DIR/$APP_NAME.sif" "$@"
}

# Pass arguments to the script
case $1 in
    (base)
        base
        ;;
    (build)
        build
        ;;
    (run)
        shift
        run "$@"
        ;;
    (*) exit 1
esac
