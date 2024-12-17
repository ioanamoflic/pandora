import sys

from pandora.pandora import Pandora

if __name__ == "__main__":
    pandora_obj = Pandora(max_time=3600)
    if len(sys.argv) == 1:
        sys.exit(0)

    if sys.argv[1] == "adder":
        # n_bits = [8, 16, 32, 64, 128, 256, 512, 1024, 2048]
        n_bits = int(sys.argv[2])
        for bits in range(n_bits):
            pandora_obj.benchmark_maslov_adder(bits)

    elif sys.argv[1] == "tket":
        print("tket")