import json

from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello World'

@app.route('/get_nr_slices')
def get_nr_slices():
    return "100"

@app.route('/get_slice/<nr>')
def get_slice(nr):
    with open("/Users/palera1/Library/Application Support/minetest/mods/minetest/n_output.json") as f:
        d = json.load(f)
        return d

# main driver function
if __name__ == '__main__':

    # run() method of Flask class runs the application
    # on the local development server.
    app.run()