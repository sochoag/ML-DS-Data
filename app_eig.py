import dash
from dash import dcc, html, Input, Output, exceptions
import numpy as np
import pandas as pd
import datetime
from datetime import datetime as dt
import pathlib
import plotly.express as px

# Funcion para limpieza de datos
def preprocesamiento(df):
    # Llenar las categorias vacias con 'No Identificado'
    df["Admit Source"] = df["Admit Source"].fillna("Not Identified")
    # Date
    # Formateo "checkin Time"
    df["Check-In Time"] = df["Check-In Time"].apply(
        lambda x: dt.strptime(x, "%Y-%m-%d %I:%M:%S %p")
    )  # String -> Datetime

    # Insertar día de la semana y hora del "Checking time"
    df["Days of Wk"] = df["Check-In Hour"] = df["Check-In Time"]
    df["Days of Wk"] = df["Days of Wk"].apply(
        lambda x: dt.strftime(x, "%A")
    )  # Datetime -> weekday string

    df["Check-In Hour"] = df["Check-In Hour"].apply(
        lambda x: dt.strftime(x, "%I %p")
    )  # Datetime -> int(hour) + AM/PM

    return df

# URL para el 
BASE_PATH = pathlib.Path(__file__).parent.resolve()
DATA_PATH = BASE_PATH.joinpath("data").resolve()

# Leer los datos y limpiarlos
df = pd.read_csv(DATA_PATH.joinpath("clinical_analytics.csv.gz"))
# Realizar preprocesamiento de fecha
df = preprocesamiento(df)

# Se guardan los valores unicos y etiquetas para sus posterior uso en la carta de control
clinic_list = df['Clinic Name'].unique()
admit_list = df['Admit Source'].unique().tolist()
day_list = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

check_in_duration = df["Check-In Time"].describe()

all_departments = df["Department"].unique().tolist()
wait_time_inputs = [Input((i + "_wait_time_graph"), "selectedData") for i in all_departments]
score_inputs = [Input((i + "_score_graph"), "selectedData") for i in all_departments]


# Se crea una estructura para la parte de la descripcion, compuesta por un H3, H5, y un Div
def description_card():
    return html.Div(
        id="description-card",
        children=[
            html.H5("Análisis operativa Clínica"),
            html.H3("Bienvenido al Dasboard de análisis de la operativa clínica"),
            html.Div(
                id="intro",
                children="Explore el volumen de pacientes por hora de día, tiempo de espera y puntuación de la atención. Haga click en el mapa térmico para visualizar la experiencia del paciente en distintos momentos.",
            ),
        ],
    )


# Se crea la estructura para la parte de control izquierda, esta se compone por un Div que contiene:
# - Una lista desplegable (Dropdown)
# - Un selector de fecha (DatePickerRange)
# - Una lista desplegable múltiple (Dropdown) con la opcion de multiple en True
# Estos controles se llenan con las variables clinic_list y admit_list
def generate_control_card():
    return html.Div(
        id="control-card",
        children=[
            html.P("Clinica"),
            dcc.Dropdown(
                id="clinic-select",
                options=[{"label": i, "value": i} for i in clinic_list],
                value=clinic_list[0],
            ),
            html.Br(),
            html.P("Fecha"),
            dcc.DatePickerRange(
                id="date-picker-select",
                start_date=dt(2014, 1, 1),
                end_date=dt(2014, 1, 15),
                min_date_allowed=dt(2014, 1, 1),
                max_date_allowed=dt(2014, 12, 31),
                initial_visible_month=dt(2014, 1, 1),
            ),
            html.Br(),
            html.Br(),
            html.P("Tipo de admisión"),
            dcc.Dropdown(
                id="admit-select",
                options=[{"label": i, "value": i} for i in admit_list],
                value=admit_list[:],
                multi=True,
            ),
            html.Br(),
        ],
    )    

# Se crea la función que generará el mapa de calor en base a la selección de parametros

def generate_patient_volume_heatmap(start, end, clinic, hm_click, admit_type, reset):

    # Filtramos el dataframe, en base a los parametros seleccionados de la card de control

    filtered_df = df[
        (df["Clinic Name"] == clinic) & (df["Admit Source"].isin(admit_type))
    ]

    # Ordenamos los valores en base al tiempo y extraemos solamente los que esten dentro del rango de inicio y fin seleccionado

    filtered_df = filtered_df.sort_values("Check-In Time").set_index("Check-In Time")[
        start:end
    ]

    # Definimos los ejes del mapa de calor
    # Eje X → Horas del dia desde 12 AM a 11 PM
    # Eje Y → Días de la semana

    x_axis = [datetime.time(i).strftime("%I %p") for i in range(24)]  # 24hr time list
    y_axis = day_list

    hour_of_day = ""
    weekday = ""

    # Si no existe ninguna seleccion simplemente no se realiza un highlight del valor

    if hm_click is not None:
        hour_of_day = hm_click["points"][0]["x"]
        weekday = hm_click["points"][0]["y"]


    # Obtenemos los valores correspondientes a las anotaciones, es decir la suma de records correspondiente para cada dia y hora

    z = np.zeros((7, 24))
    annotations = []

    for ind_y, day in enumerate(y_axis):
        filtered_day = filtered_df[filtered_df["Days of Wk"] == day]
        for ind_x, x_val in enumerate(x_axis):
            sum_of_record = filtered_day[filtered_day["Check-In Hour"] == x_val][
                "Number of Records"
            ].sum()
            z[ind_y][ind_x] = sum_of_record

            annotation_dict = dict(
                showarrow=False,
                text="<b>" + str(sum_of_record) + "<b>",
                xref="x",
                yref="y",
                x=x_val,
                y=day,
                font=dict(family="sans-serif"),
            )

            # En caso de que exista algun valor seleccionado, se realizara un highlight de color blanco y se aumentará el tamaño de fuente

            if x_val == hour_of_day and day == weekday:
                if not reset:
                    annotation_dict.update(size=18, font=dict(size=20,color="#FFFFFF"))

            annotations.append(annotation_dict)

    # Se guarda dentro del array data el diccionario que posteriormente indicara de donde tomar los datos, 
    # el tipo de grafica y sus colores al momento de renderizarlp

    data = [
        dict(
            x=x_axis,
            y=y_axis,
            z=z,
            type="heatmap",
            showscale=False,
            colorscale=[[0, "#caf3ff"], [1, "#2c82ff"]],
        )
    ]

    # En el diccionario layout se configura varios parametros esteticos como los margenes, orientación, etc.

    layout = dict(
        margin=dict(l=70, b=50, t=50, r=50),
        modebar={"orientation": "v"},
        font=dict(family="Open Sans"),
        annotations=annotations,
        xaxis=dict(
            side="top",
            ticks="",
            ticklen=2,
            tickfont=dict(family="sans-serif"),
            tickcolor="#ffffff",
        ),
        yaxis=dict(
            side="left", ticks="", tickfont=dict(family="sans-serif"), ticksuffix=" "
        ),
        hovermode="closest",
        showlegend=False,
    )
    return {"data": data, "layout": layout}


# Se crea la función que generará el grafico de boxplot en base a la selección de heatmap
# Para controlar esto se ocupa el parametro hm_click el cual tendra un valor de None en caso de
# que no haya existido previa interacción con el mapa de calor, adicionalmente, el parametro reset
# hace que la grafica se limpia cuando hay interacción con el boton "Limpiar" situado abajo del mapa
# de calor

def generate_waiting_time_by_department_chart(start, end, clinic, hm_click, admit_type, reset):

    hour = None
    day = None

    # Logica para determinar si se debe o no renderizar el grafico

    if (hm_click is None) | (reset):
        fig = {}
        return fig
    else:
        hour= hm_click['points'][0]['x']
        day= hm_click['points'][0]['y']


    # Se realiza el filtrado en base al valor escogido en el mapa de calor, tomando en cuenta tambien el filtro previo

    filtered_df = df[(df['Check-In Hour']==hour) & (df['Days of Wk']==day)]

    filtered_df = filtered_df[
        (filtered_df["Clinic Name"] == clinic) & (filtered_df["Admit Source"].isin(admit_type))
    ]

    filtered_df = filtered_df.sort_values("Check-In Time").set_index("Check-In Time")[
        start:end
    ]

    # Se guarda y retorna la figura

    fig = px.box(filtered_df, x='Department', y='Wait Time Min', points='all', color='Department')

    return fig

# Lo mismo sucede con el segundo grafico de boxplot para el score por departamentos.

def generate_score_by_department_chart(start, end, clinic, hm_click, admit_type, reset):
    
    hour = None
    day = None

    # Logica para determinar si se debe o no renderizar el grafico

    if (hm_click is None) | (reset):
        fig = {}
        return fig
    else:
        hour= hm_click['points'][0]['x']
        day= hm_click['points'][0]['y']

    # Se realiza el filtrado en base al valor escogido en el mapa de calor, tomando en cuenta tambien el filtro previo

    filtered_df = df[(df['Check-In Hour']==hour) & (df['Days of Wk']==day)]

    filtered_df = filtered_df[
        (filtered_df["Clinic Name"] == clinic) & (filtered_df["Admit Source"].isin(admit_type))
    ]

    filtered_df = filtered_df.sort_values("Check-In Time").set_index("Check-In Time")[
        start:end
    ]

    # Se guarda y retorna la figura

    fig = px.box(filtered_df, x='Department', y='Care Score', points='all', color='Department')

    return fig


#####################################################

# Estructura de la app

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": 
                "width=device-width, initial-scale=1"}],
)

# Titulo de la aplicacion

app.title = "Tablero de control clinico"

# app.layout contiene toda la estructura de la aplicación

app.layout = html.Div(
    id = "app-container",
    children=[
        # Banner
        html.Div
        (
            id="banner",
            className="banner",
            children=[html.Img(src=app.get_asset_url("eig_logo.png"))],
        ),
        # Columna izquierda
        html.Div
        (
            id="left-column",
            className="four columns",
            children=[description_card(), generate_control_card()]
            + [
                html.Div
                (
                    ["initial child"], id="output-clientside", style={"display": "none"}
                )
            ],
        ),
            # Columna derecha
        html.Div
        (
            id="right-column",
            className="eight columns",
            children=
            [
                # Sección de mapa de calor de pacientes
                html.Div
                (
                    id="patient_volume_card",
                    children=[
                        html.B("Volumen de pacientes"),
                        html.Hr(),
                        dcc.Graph(id="patient_volume_hm"),
                        html.Div(
                            id="reset-btn-outer",
                            children=html.Button(id="reset-btn", children="Limpiar", n_clicks=0), 
                        )
                        ,
                    ],
                ),
                # Sección de Distribucion de tiempo de espera por departamento
                html.Div(
                    id="wait_time_card",
                    children=[
                        html.B("Distribucion de tiempo de espera por departamento"),
                        html.Hr(),
                        html.Div(children=dcc.Graph(id="wait_time_table")),
                    ],
                ),
                # Sección de Distribucion de puntajes de calificacion por departamento
                html.Div(
                    id="socre_card",
                    children=[
                        html.B("Distribucion de puntajes de calificacion por departamento"),
                        html.Hr(),
                        html.Div(children=dcc.Graph(id="score_table")),
                    ],
                ),
            ]
        )
    ]
)


# Se crea un callback el cual será encargado de modificar las graficas en base a las interacciones, este callback posee las siguientes
# entradas y salidas
#
# Entradas
# - Selector de fecha (date-picker-select)(start-date)
# - Selector de fecha (date-picker-select)(end-date)
# - Selector de clinica (clinic-select)(value)
# - Metadatos de interacción con el mapa de calor (patient_volume_hm)(clickData)
# - Selector de tipo de admision (admit-select)(value)
# - Boton de limpieza (reset-btn)(n_clicks)
#
# Salidas
# - Grafico de mapa de calor de pacientes (patient_volume_hm)(figure)
# - Grafico de boxplot de tiempo de espera por departamento (wait_time_table)(figure)
# - Grafico de boxplot de puntaje por departamento (score_table)(figure)

@app.callback([
    Output("patient_volume_hm", "figure"),
    Output("wait_time_table",'figure'),
    Output("score_table", 'figure')],
    [
        Input("date-picker-select", "start_date"),
        Input("date-picker-select", "end_date"),
        Input("clinic-select", "value"),
        Input("patient_volume_hm", "clickData"),
        Input("admit-select", "value"),
        Input("reset-btn", "n_clicks"),
    ],
)

# Funcion que se ejecuta al interactuar con cualquiera de las entradas

def update_charts(start, end, clinic, hm_click, admit_type, reset_click):

    # Se agrega el valor de hh:mm:ss a la fecha seleccionada para su posterior filtrado

    start = start + " 00:00:00"
    end = end + " 00:00:00"

    # Se inicializa una bandera para el boton de reset o limpieza

    reset = False
    
    # Se obtiene el contexto dentro de la aplicacion 
    ctx = dash.callback_context

    # En caso de que se haya disparado el contexto, se verifica si el causante de ello fue el boton de reset
    if ctx.triggered:
        prop_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # En caso de que reset se ha dado click, levantamos la bandera, para su posterior manejo en las funciones que generan los gráficos

        if prop_id == "reset-btn":
            reset = True

    # Se almacenan el fig1, fig2 y fig3 los datos necesarios para renderizarlo dentro de la aplicación

    fig1 = generate_patient_volume_heatmap(start, end, clinic, hm_click, admit_type, reset)
    fig2 = generate_waiting_time_by_department_chart(start, end, clinic, hm_click, admit_type, reset)
    fig3 = generate_score_by_department_chart(start, end, clinic, hm_click, admit_type, reset)

    return fig1, fig2, fig3


# Se ejecuta el servidor en el puerto 8080

if __name__ == "__main__":
    app.run_server(debug=True, port=8080)
