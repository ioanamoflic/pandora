import sys

from pandora import Pandora

if __name__ == "__main__":

    if len(sys.argv) == 1:
        sys.exit(0)

    pandora = Pandora(max_time=3600)

    if sys.argv[1] == "adder":
        # n_bits = [8, 16, 32, 64, 128, 256, 512, 1024, 2048]
        n_bits = [int(sys.argv[2])]

        for bits in n_bits:
            pandora.build_maslov_adder(bits)

    elif sys.argv[1] == "tket":
        print("tket")