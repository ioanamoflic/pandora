#!/usr/bin/env bash
set -eu
# Resolve the recipe, base image, and %files sources relative to this script.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
IMAGES_DIR="images"

# the name of the docker image to start from
BASE_IMAGE="postgres:latest"

# the name of the project
APP_NAME="pandora"

build() {
    mkdir -p "$IMAGES_DIR"
    apptainer build "$IMAGES_DIR/$APP_NAME.sif" project.apptainer
}

run() {
    apptainer run "$IMAGES_DIR/$APP_NAME.sif" "$@"
}

# Pass arguments to the script
case $1 in
    (build)
        build
        ;;
    (run)
        shift
        run "$@"
        ;;
    (*) exit 1
esac
