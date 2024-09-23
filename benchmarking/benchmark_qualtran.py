import csv
from cirq2db_test import test_qualtran_qrom_reconstruction, test_qualtran_adder_reconstruction, \
    test_qualtran_qpe_reconstruction

if __name__ == "__main__":
    times = test_qualtran_adder_reconstruction()
    # times = test_qualtran_qrom_reconstruction()
    # times = test_qualtran_qpe_reconstruction()
    with open(f'results/qualtran_reconstruction.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)
