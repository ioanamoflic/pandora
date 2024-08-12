import random

import psycopg2

from benchmarking import benchmark_cirq
from cirq2db import *
from _connection import *
from main import db_multi_threaded
from qualtran2db import *
import numpy as np

connection = psycopg2.connect(
    database="postgres",
    # user="postgres",
    host="localhost",
    port=5432,
    password="1234")

cursor = connection.cursor()
connection.set_session(autocommit=True)

if connection:
    print("Connection to the PostgreSQL established successfully.")
else:
    print("Connection to the PostgreSQL encountered and error.")


def test_ancillify_measure_and_reset():
    return NotImplementedError()


def test_cnotify_XX():
    return NotImplementedError()


def test_cnotify_ZZ():
    return NotImplementedError()


def test_cxor0xora():
    return NotImplementedError()


def test_decompose_n22_weight_stabilizer():
    return NotImplementedError()


def test_lscx_down_a():
    return NotImplementedError()


def test_lscx_down_b():
    return NotImplementedError()


def test_lscx_up_a():
    return NotImplementedError()


def test_lscx_up_b():
    return NotImplementedError()


def test_simplify_erasure_error():
    return NotImplementedError()


def test_simplify_two_parity_check():
    return NotImplementedError()


def test_useless_cx_ancilla_zero_X():
    return NotImplementedError()


def test_useless_cx_ancilla_plus_Z():
    return NotImplementedError()


def test_useless_cx_ctrl_zero():
    return NotImplementedError()


def test_useless_cx_plusplus():
    return NotImplementedError()


def test_useless_cx_plus_Z():
    return NotImplementedError()


def test_useless_cx_zero_X():
    return NotImplementedError()
