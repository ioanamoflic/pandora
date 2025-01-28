import sys
import psycopg2

connection_list = []


def create_connections(file_name, user_name):
    with open(file_name, 'r') as file:
        for i, host_name in enumerate(file):
            connection = psycopg2.connect(
                dbname="postgres",
                user=user_name,
                host=host_name,
                port=5432,
                password="1234")

            connection.set_session(autocommit=True)

            if connection:
                connection_list.append(connection)
            else:
                print(f"Connection to {host_name} failed!")


def collect(gate_type):
    sql = "select count(*) from linked_circuit"
    if gate_type is not None:
        sql = sql + f" where type='{gate_type}'"

    for connection in connection_list:
        cursor = connection.cursor()
        cursor.execute(sql)

        result = cursor.fetchall()
        print(connection.info.host, result)


if __name__ == '__main__':
    fname = None
    uname = None
    gtype = None

    if len(sys.argv) >= 2:
        fname = sys.argv[1]

    if len(sys.argv) >= 3:
        uname = sys.argv[2]

    if len(sys.argv) >= 4:
        gtype = sys.argv[3]

    create_connections(fname, uname)

    while True:
        collect(gtype)
