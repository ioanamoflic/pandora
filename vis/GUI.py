import pandas as pd
import dash
from dash import dcc
from dash import html
import plotly.express as px
from dash.dependencies import Output, Input

from pandora.connection_util import get_connection

app = dash.Dash(__name__)
app.title = "Pandora Optimiser"

app.layout = [
    html.Div([
        html.H1(children='Pandora Optimiser', style={'textAlign': 'center', "margin-top": "20px"}),
        html.Div(
            dcc.Dropdown(['Adder8', 'Adder16', 'Adder32'], 'Adder8', id='dropdown-selection',
                         style={
                             "background-color": "#A9A9A9",
                             "color": "black",
                         }),
            style={
                "width": "50%",
                "height": "50%",
                "margin-left": "auto",
                "margin-right": "auto",
                "margin-bottom": "20px",
                "margin-top": "20px",
            },
        ),
        dcc.Graph(id='main_optimizer',
                  style={
                      "width": "50%",
                      "height": "50%"
                  }
                  ),
        dcc.Graph(id='percentage',
                  style={
                      "width": "50%",
                      "height": "50%"
                  }
                  ),
        dcc.Interval(
            id='interval-component',
            interval=5 * 1000,
            n_intervals=0,
        )
    ],
        style={
            "width": "50%",
            "height": "50%",
            "margin-left": "auto",
            "margin-right": "auto",
        },
    )
]


@app.callback(
    Output(component_id='main_optimizer', component_property='figure'),
    Input('interval-component', 'n_intervals'),
    Input('dropdown-selection', 'value')
)
def update_graph(n_intervals, value):
    conn = get_connection()

    df = pd.read_sql_query("select * from optimization_results", conn)
    conn.close()

    fig = px.line(data_frame=df,
                  x=df.index,
                  y=["total_count", "t_count", "s_count", "h_count", "cx_count", "x_count"],
                  width=800,
                  height=600,)
    return fig


@app.callback(
    Output(component_id='percentage', component_property='figure'),
    Input('interval-component', 'n_intervals'),
)
def update_graph2(n_intervals):
    columns = ["total_count", "t_count", "s_count", "h_count", "cx_count", "x_count"]

    conn = get_connection()

    df = pd.read_sql_query("select * from optimization_results", conn)
    conn.close()

    for i in range(1, len(df)):

        for col in columns:
            val = df[col].iloc[0]
            if val > 0:
                df.loc[i, col] /= val

    for col in df.columns:
        df[col].iloc[0] = 1

    fig = px.line(data_frame=df,
                  x=df.index,
                  y=columns,
                  width=800,
                  height=600)
    return fig


if __name__ == '__main__':
    app.run(debug=True)
