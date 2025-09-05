.PHONY: all pandora


all: pandora

pandora:
	cd apptainer;  \
	./apptainer_util.sh base; \
	./apptainer_util.sh build; \

test:

clean:

