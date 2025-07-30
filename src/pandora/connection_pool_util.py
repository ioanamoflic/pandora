from pandora.connection_util import get_connection

connection = None


def init_worker(config_file_path):
    global connection
    connection = get_connection(config_file_path=config_file_path)
    connection.set_session(autocommit=True)


def map_procedure_call(proc_call):
    global connection
    cursor = connection.cursor()
    cursor.execute(proc_call)
    cursor.close()
