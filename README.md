# Agente de Vigilancia - API Propia

API independiente del agente de vigilancia, lista para Render.
NO toca ni depende del servicio de catastro ni del de semaforos
del equipo. Para leer semaforos, cuando el compañero de ese
agente suba su propia API, solo se consume igual que hicimos
con catastro_remoto.py (GET a su endpoint).

## Estructura

```
vigilancia_render/
  app.py             <- servidor Flask, todos los endpoints
  base_datos.py       <- SQLite (papeletas, vehiculos, eventos)
  notificador.py        <- sistema de webhooks
  requirements.txt
  Procfile
  render.yaml
```

## Subir a Render

1. Repo nuevo en GitHub con estos archivos
2. render.com -> New + -> Web Service -> conectar el repo
3. Esperar 2-3 min, te da una URL como:
   https://vigilancia-api-XXXX.onrender.com

## Endpoints nuevos (ademas de los de antes)

### POST /api/vigilancia/suscribir
Otro agente (centro de control, vehiculos) registra su webhook
para recibir notificaciones automaticas.

Body:
```json
{
    "nombre_agente": "centro_control",
    "url_webhook": "https://centro-control-xxxx.onrender.com/webhook/vigilancia"
}
```

### POST /api/vigilancia/desuscribir
Body: `{"nombre_agente": "centro_control"}`

### GET /api/vigilancia/suscriptores
Lista quien esta suscrito actualmente.

## Como funciona la notificacion automatica

Cuando `/api/vigilancia/inspeccionar` detecta una infraccion,
o `/api/vigilancia/colision` detecta un choque, el sistema
automaticamente hace POST a cada webhook suscrito con:

```json
{
    "evento": "INFRACCION",
    "timestamp": "2026-06-18 17:29:51",
    "data": { ...papeleta completa... }
}
```

o para colisiones:

```json
{
    "evento": "COLISION",
    "timestamp": "...",
    "data": {
        "vehiculos": ["AV-01", "AV-02"],
        "distancia_px": 15.2,
        "nodo": "...",
        "detalle": "...",
        "papeletas": [...]
    }
}
```

Si el webhook de un agente no responde (esta dormido en Render
free tier, o no existe todavia), vigilancia sigue funcionando
normal, solo registra el fallo en consola.

## Que necesita el centro de control para recibir avisos

Su propio servidor Flask necesita un endpoint asi:

```python
@app.route("/webhook/vigilancia", methods=["POST"])
def recibir_aviso_vigilancia():
    data = request.get_json()
    print(f"Aviso de vigilancia: {data['evento']}")
    # guardar en su DB, mostrar en su dashboard, etc.
    return jsonify({"recibido": True})
```

Y luego se suscribe llamando a tu API:

```python
import requests
requests.post(
    "https://TU-URL.onrender.com/api/vigilancia/suscribir",
    json={
        "nombre_agente": "centro_control",
        "url_webhook": "https://SU-URL.onrender.com/webhook/vigilancia"
    }
)
```
