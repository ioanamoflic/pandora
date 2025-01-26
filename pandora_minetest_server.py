import json

import sys

from flask import Flask

from pandora import Pandora, PandoraConfig
from pandora.exceptions import TupleNotFound

app = Flask(__name__)

#Load default config
config = PandoraConfig()
pandora = Pandora(pandora_config=config, max_time=3600)

@app.route('/')
def hello_world():
    return 'Hello World'


@app.route('/get_nr_slices')
def get_nr_slices():

    connection = pandora.get_connection()
    cursor = connection.cursor()

    sql_statement = "select count(id) from minetest"
    cursor.execute(sql_statement)
    res = cursor.fetchone()

    return str(res[0])


@app.route('/get_slice/<nr>')
def get_slice(nr):
    # with open("dummy.json") as f:
    #     d = json.load(f)
    #     return d

    connection = pandora.get_connection()
    cursor = connection.cursor()

    # tnr = (int(nr) % 6) + 1

    tnr = int(nr)
    sql_statement = f"select json from minetest where id={tnr}"
    cursor.execute(sql_statement)
    res = cursor.fetchone()

    if res is None:
        raise TupleNotFound

    return "[" + str(res[0]) + "]"

# main driver function
if __name__ == '__main__':
    # run() method of Flask class runs the application
    # on the local development server.
    app.run()
