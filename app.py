from flask import Flask, request, jsonify, render_template
from flask_httpauth import HTTPBasicAuth
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime as dt
import os

from dotenv import load_dotenv

# Importy do Dash
import dash
from dash import dcc, html
import plotly.graph_objs as go
from dash.dependencies import Input, Output

load_dotenv()

# Flask i HTTPAuth setup
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
auth = HTTPBasicAuth()

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Prosta baza użytkowników i haseł
users = {
    "user": generate_password_hash(os.getenv('USER_PASSWORD'))
}

class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.String(50), nullable=False)  # ID sensora
    key = db.Column(db.String(50), nullable=False)  # Klucz np. 'temp', 'hum'
    value = db.Column(db.Float, nullable=False)  # Wartość np. 21.5, 60.2
    timestamp = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)  # Czas pomiaru

    def __repr__(self):
        return f'<SensorData {self.sensor_id} - {self.key}: {self.value}>'

# Sprawdzanie danych logowania
@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None

# Endpoint do zapisywania nowego pomiaru
@app.route('/add_measurement', methods=['POST'])
@auth.login_required
def add_measurement():
    data = request.get_json()
    sensor_id = data.get('sensor_id')
    key = data.get('key')  # np. 'temp'
    value = data.get('value')  # np. 21.5
    
    if not sensor_id or not key or value is None:
        return jsonify({"error": "Missing sensor_id, key, or value"}), 400

    timestamp = data.get('timestamp')
    if timestamp:
        new_measurement = SensorData(sensor_id=sensor_id, key=key, value=value, timestamp=timestamp) 
    else:
        new_measurement = SensorData(sensor_id=sensor_id, key=key, value=value)
    db.session.add(new_measurement)
    db.session.commit()
    
    return jsonify({"message": f"Measurement added for sensor '{sensor_id}' with key '{key}' and value {value}"}), 201

# Endpoint do pobierania pomiarów dla sensora
@app.route('/get_measurements/<sensor_id>', methods=['GET'])
@auth.login_required
def get_measurements(sensor_id):
    measurements = SensorData.query.filter_by(sensor_id=sensor_id).all()
    
    if not measurements:
        return jsonify({"error": f"No measurements found for sensor '{sensor_id}'"}), 404

    return jsonify([{
        "sensor_id": measurement.sensor_id,
        "key": measurement.key,
        "value": measurement.value,
        "timestamp": measurement.timestamp
    } for measurement in measurements])

# Dash integracja
dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dash/')

# Layout dla Dash (bez zapytania do bazy na tym etapie)
dash_app.layout = html.Div([
    html.H1("Sensor Data Visualization"),
    
    # Dropdown do wyboru sensora (początkowo pusty)
    dcc.Dropdown(
        id='sensor-dropdown',
        options=[],  # Pusty na starcie, uzupełnimy go w callbacku
        placeholder="Select a Sensor",
        value=None
    ),
    
    # Miejsce na wykresy
    html.Div(id='graphs-container')
])

# Callback do uzupełnienia dropdowna z sensorami (zapytanie do bazy)
@dash_app.callback(
    Output('sensor-dropdown', 'options'),
    [Input('sensor-dropdown', 'value')]
)
def update_sensor_dropdown(_):
    with app.app_context():  # Używamy kontekstu aplikacji Flask
        sensors = SensorData.query.distinct(SensorData.sensor_id).all()
        options = [{'label': sensor.sensor_id, 'value': sensor.sensor_id} for sensor in sensors]
    return options

# Callback do generowania wykresów
@dash_app.callback(
    Output('graphs-container', 'children'),
    [Input('sensor-dropdown', 'value')]
)
def update_graphs(sensor_id):
    if sensor_id is None:
        return html.Div("Please select a sensor to display data.")
    
    with app.app_context():  # Zapytania w kontekście aplikacji Flask
        measurements = SensorData.query.filter_by(sensor_id=sensor_id).all()

    if not measurements:
        return html.Div(f"No data found for sensor {sensor_id}.")

    # Grupowanie po 'key' dla danego sensor_id
    keys = set([m.key for m in measurements])
    
    graphs = []
    for key in keys:
        key_data = [m for m in measurements if m.key == key]
        x = [m.timestamp for m in key_data]
        y = [m.value for m in key_data]
        
        graph = dcc.Graph(
            figure={
                'data': [
                    go.Scatter(x=x, y=y, mode='lines+markers', name=key)
                ],
                'layout': go.Layout(
                    title=f"{key} measurements for {sensor_id}",
                    xaxis={'title': 'Timestamp'},
                    yaxis={'title': key},
                    margin={'l': 40, 'b': 40, 't': 40, 'r': 0},
                    hovermode='closest'
                )
            }
        )
        graphs.append(graph)
    
    return graphs

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
