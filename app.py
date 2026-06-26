# -*- coding: utf-8 -*-
"""
=============================================================
  API DEL AGENTE DE VIGILANCIA (FastAPI)
  Sistema Multi-Agente de Transito - FINESI UNAP
=============================================================
  Migrado de Flask a FastAPI para generar documentacion
  Swagger/OpenAPI automaticamente desde los tipos de Python
  (Pydantic), igual que la API de Vehiculos y Catastro del
  equipo.

  Expone:
    - Inspeccion de vehiculos / emision de papeletas
    - Deteccion y registro de colisiones
    - Sistema de notificacion FIPA-ACL hacia otros agentes
      (Centro de Control, Vehiculos)

  Documentacion interactiva: /docs
  Especificacion OpenAPI:    /openapi.json
=============================================================
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

import base_datos as db
import notificador


# -----------------------------------------------
#  CONFIGURACION DE LA APP
# -----------------------------------------------

app = FastAPI(
    title="API Agente Vigilancia",
    description=(
        "Modulo de vigilancia del Sistema Multi-Agente de Transito Urbano. "
        "Detecta infracciones (velocidad, semaforo, SOAT, colisiones), emite "
        "papeletas y notifica a otros agentes (Centro de Control, Vehiculos) "
        "usando el protocolo formal FIPA-ACL. Compatible con las APIs de "
        "Mapas, Semaforos y Vehiculos del equipo."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LIMITE_VELOCIDAD   = 50
PESO_MAXIMO_TN     = 3.5
DISTANCIA_COLISION = 20   # px
DISTANCIA_RIESGO   = 40   # px

MONTOS = {
    "EXCESO DE VELOCIDAD"         : 200.0,
    "PASO EN ROJO"                : 350.0,
    "PASO IMPRUDENTE EN AMARILLO" : 150.0,
    "EXCESO DE PESO"              : 450.0,
    "VEHICULO NO AUTORIZADO"      : 300.0,
    "COLISION"                    : 800.0,
}

db.inicializar()


# -----------------------------------------------
#  MODELOS (Pydantic) -> generan la documentacion sola
# -----------------------------------------------

class InspeccionRequest(BaseModel):
    id_veh: str = Field(..., example="AV-01", description="Placa o ID del vehiculo")
    velocidad_kmh: float = Field(0, example=65, description="Velocidad actual en km/h")
    peso_tn: float = Field(1.0, example=1.2, description="Peso del vehiculo en toneladas")
    semaforo_estado: str = Field("VERDE", example="ROJO", description="VERDE, AMARILLO o ROJO")
    nodo: str = Field("Via publica", example="NODO NO (San Martin)")
    distrito: str = Field("centro", example="centro")
    autorizado: bool = Field(True, example=True)


class ColisionRequest(BaseModel):
    id_veh_a: str = Field(..., example="AV-01")
    id_veh_b: str = Field(..., example="AV-02")
    distancia_px: float = Field(999, example=15.2)
    velocidad_a_kmh: float = Field(0, example=40)
    velocidad_b_kmh: float = Field(0, example=35)
    nodo: str = Field("Via publica", example="NODO NO (San Martin)")
    distrito: str = Field("centro", example="centro")


class RegistrarVehiculoRequest(BaseModel):
    id_veh: str = Field(..., example="AV-03")
    peso_tn: float = Field(1.0, example=2.5)
    autorizado: bool = Field(True, example=True)
    propietario: str = Field("Desconocido", example="Juan Perez")


class SuscripcionRequest(BaseModel):
    nombre_agente: str = Field(..., example="centro_control")
    url_webhook: str = Field(..., example="https://centro-control-xxxx.onrender.com/webhook/vigilancia")


class DesuscripcionRequest(BaseModel):
    nombre_agente: str = Field(..., example="centro_control")


# -----------------------------------------------
#  INFO / RAIZ
# -----------------------------------------------

@app.get("/", tags=["Info"], summary="Info general de la API")
def index():
    """Lista de endpoints disponibles y version del servicio."""
    return {
        "servicio": "Agente de Vigilancia - Sistema MAS Transito",
        "version": "3.0.0",
        "framework": "FastAPI",
        "documentacion": "/docs",
    }


# -----------------------------------------------
#  ESTADO / REPORTES
# -----------------------------------------------

@app.get("/api/vigilancia/estado", tags=["Estado"], summary="Estado general del agente")
def estado():
    """Limites configurados, multas totales, vehiculos y suscriptores activos."""
    return {
        "limite_velocidad_kmh": LIMITE_VELOCIDAD,
        "peso_maximo_tn": PESO_MAXIMO_TN,
        "total_multas_s": db.total_multas(),
        "vehiculos_registrados": db.obtener_todos_vehiculos(),
        "suscriptores_activos": notificador.listar_suscriptores(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/api/vigilancia/papeletas", tags=["Papeletas"], summary="Lista de papeletas emitidas")
def papeletas(
    id_veh: Optional[str] = Query(None, description="Filtrar por placa/id del vehiculo"),
    distrito: Optional[str] = Query(None, description="Filtrar por distrito"),
    limite: int = Query(50, description="Cantidad maxima de resultados"),
):
    """Retorna las papeletas emitidas, con filtros opcionales."""
    return db.obtener_papeletas(id_veh=id_veh, distrito=distrito, limite=limite)


@app.get("/api/vigilancia/reportes", tags=["Reportes"], summary="Reportes agrupados de infracciones")
def reportes():
    """Reportes por vehiculo, tipo de infraccion y distrito."""
    return {
        "por_vehiculo": db.reporte_por_vehiculo(),
        "por_tipo":     db.reporte_por_tipo(),
        "por_distrito": db.reporte_por_distrito(),
        "total_recaudado_s": db.total_multas(),
    }


@app.get("/api/vigilancia/eventos", tags=["Reportes"], summary="Log de eventos del agente")
def eventos(limite: int = Query(20, description="Cantidad maxima de eventos")):
    """Retorna los ultimos eventos registrados por el agente."""
    return db.obtener_eventos(limite)


@app.get("/api/vigilancia/vehiculos", tags=["Vehiculos"], summary="Vehiculos registrados localmente")
def vehiculos():
    """Lista de vehiculos registrados en la base local de vigilancia."""
    return db.obtener_todos_vehiculos()


# -----------------------------------------------
#  INSPECCION / PAPELETAS
# -----------------------------------------------

@app.post("/api/vigilancia/inspeccionar", tags=["Inspeccion"],
          summary="Inspecciona un vehiculo y emite papeletas si hay infracciones")
def inspeccionar(data: InspeccionRequest):
    """
    Evalua velocidad, semaforo, peso y autorizacion de un vehiculo.
    Si detecta infracciones, las guarda y notifica via FIPA-ACL
    (performativa INFORM) a todos los agentes suscritos.
    """
    id_veh     = data.id_veh
    vel_kmh    = data.velocidad_kmh
    peso_tn    = data.peso_tn
    sem_estado = data.semaforo_estado
    nodo       = data.nodo
    distrito   = data.distrito
    autorizado = data.autorizado

    if db.obtener_vehiculo(id_veh) is None:
        db.registrar_vehiculo(id_veh, peso_tn, autorizado, "Desconocido")

    infracciones = []

    if vel_kmh > LIMITE_VELOCIDAD:
        infracciones.append(_crear_papeleta(
            id_veh, "EXCESO DE VELOCIDAD",
            f"Vel: {vel_kmh}km/h | Limite: {LIMITE_VELOCIDAD}km/h",
            vel_kmh, peso_tn, nodo, distrito
        ))

    if sem_estado == "ROJO" and vel_kmh > 10:
        infracciones.append(_crear_papeleta(
            id_veh, "PASO EN ROJO",
            f"{id_veh} circulo con semaforo en ROJO a {vel_kmh}km/h",
            vel_kmh, peso_tn, nodo, distrito
        ))
    elif sem_estado == "AMARILLO" and vel_kmh > 40:
        infracciones.append(_crear_papeleta(
            id_veh, "PASO IMPRUDENTE EN AMARILLO",
            f"Acelero en AMARILLO a {vel_kmh}km/h",
            vel_kmh, peso_tn, nodo, distrito
        ))

    if peso_tn > PESO_MAXIMO_TN:
        infracciones.append(_crear_papeleta(
            id_veh, "EXCESO DE PESO",
            f"Peso: {peso_tn}tn | Max: {PESO_MAXIMO_TN}tn",
            vel_kmh, peso_tn, nodo, distrito
        ))

    if not autorizado:
        infracciones.append(_crear_papeleta(
            id_veh, "VEHICULO NO AUTORIZADO",
            f"{id_veh} no figura en el registro de autorizados",
            vel_kmh, peso_tn, nodo, distrito
        ))

    return {
        "id_veh": id_veh,
        "infracciones_detectadas": len(infracciones),
        "papeletas": infracciones,
    }


@app.post("/api/vigilancia/colision", tags=["Inspeccion"],
          summary="Registra colision o riesgo de colision entre dos vehiculos")
def colision(data: ColisionRequest):
    """
    Segun la distancia entre los vehiculos:
    - menos de 20px: COLISION (emite papeleta a ambos)
    - 20 a 40px: RIESGO_COLISION (solo notifica, sin papeleta)
    - mas de 40px: SIN_RIESGO
    """
    id_a = data.id_veh_a
    id_b = data.id_veh_b
    dist = data.distancia_px
    vel_a = data.velocidad_a_kmh
    vel_b = data.velocidad_b_kmh
    nodo = data.nodo
    distrito = data.distrito

    if dist < DISTANCIA_COLISION:
        detalle = f"{id_a} y {id_b} colisionaron | Distancia: {dist}px"

        papeletas_generadas = []
        for veh_id, vel in [(id_a, vel_a), (id_b, vel_b)]:
            veh_db = db.obtener_vehiculo(veh_id)
            peso_tn = veh_db["peso_tn"] if veh_db else 1.0
            p = _crear_papeleta(veh_id, "COLISION", detalle, vel, peso_tn, nodo, distrito)
            papeletas_generadas.append(p)

        colision_info = {
            "vehiculos": [id_a, id_b],
            "distancia_px": dist,
            "nodo": nodo,
            "distrito": distrito,
            "detalle": detalle,
            "papeletas": papeletas_generadas,
        }
        notificador.notificar_colision(colision_info)
        return {"tipo": "COLISION", **colision_info}

    elif dist < DISTANCIA_RIESGO:
        detalle = f"{id_a} y {id_b} en zona de riesgo | Distancia: {dist}px"
        riesgo_info = {
            "vehiculos": [id_a, id_b],
            "distancia_px": dist,
            "nodo": nodo,
            "distrito": distrito,
            "detalle": detalle,
        }
        notificador.notificar_riesgo(riesgo_info)
        return {"tipo": "RIESGO_COLISION", **riesgo_info}

    return {"tipo": "SIN_RIESGO", "distancia_px": dist}


@app.post("/api/vigilancia/registrar", tags=["Vehiculos"],
          summary="Registra o actualiza un vehiculo")
def registrar(data: RegistrarVehiculoRequest):
    """Registra un vehiculo nuevo o actualiza uno existente en la base local."""
    db.registrar_vehiculo(data.id_veh, data.peso_tn, data.autorizado, data.propietario)
    return {
        "mensaje": f"Vehiculo {data.id_veh} registrado/actualizado",
        "vehiculo": db.obtener_vehiculo(data.id_veh),
    }


# -----------------------------------------------
#  SUSCRIPCION (notificaciones FIPA-ACL a otros agentes)
# -----------------------------------------------

@app.post("/api/vigilancia/suscribir", tags=["Comunicacion entre Agentes"],
          summary="Suscribe un agente para recibir notificaciones FIPA-ACL")
def suscribir(data: SuscripcionRequest):
    """
    Registra el webhook de otro agente (Centro de Control, Vehiculos)
    para recibir mensajes INFORM cada vez que se emita una papeleta
    o se detecte una colision.
    """
    notificador.suscribir(data.nombre_agente, data.url_webhook)
    return {
        "mensaje": f"{data.nombre_agente} suscrito correctamente",
        "suscriptores": notificador.listar_suscriptores(),
    }


@app.post("/api/vigilancia/desuscribir", tags=["Comunicacion entre Agentes"],
          summary="Desuscribe un agente de las notificaciones")
def desuscribir(data: DesuscripcionRequest):
    """Elimina a un agente de la lista de suscriptores."""
    notificador.desuscribir(data.nombre_agente)
    return {
        "mensaje": f"{data.nombre_agente} desuscrito",
        "suscriptores": notificador.listar_suscriptores(),
    }


@app.get("/api/vigilancia/suscriptores", tags=["Comunicacion entre Agentes"],
         summary="Lista de agentes suscritos")
def suscriptores():
    """Diccionario con nombre_agente como clave y url_webhook como valor."""
    return notificador.listar_suscriptores()


@app.get("/api/vigilancia/acl/historial", tags=["Comunicacion entre Agentes"],
         summary="Historial de mensajes FIPA-ACL enviados")
def acl_historial(limite: int = Query(20, description="Cantidad maxima de mensajes")):
    """
    Retorna los ultimos mensajes formales FIPA-ACL enviados por el
    agente (performative, sender, receiver, conversation_id).
    """
    return notificador.obtener_historial_acl(limite)


# -----------------------------------------------
#  UTILIDADES INTERNAS
# -----------------------------------------------

def _crear_papeleta(id_veh, tipo, detalle, vel_kmh, peso_tn, nodo, distrito):
    """Crea, guarda en DB, notifica via FIPA-ACL y retorna la papeleta."""
    numero = f"PAP-{int(datetime.now().timestamp() * 1000) % 1000000:06d}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    monto = MONTOS.get(tipo, 100.0)

    papeleta_dict = {
        "numero"   : numero,
        "timestamp": timestamp,
        "id_veh"   : id_veh,
        "tipo"     : tipo,
        "detalle"  : detalle,
        "vel_kmh"  : vel_kmh,
        "peso_tn"  : peso_tn,
        "monto_s"  : monto,
        "nodo"     : nodo,
        "distrito" : distrito,
    }

    class _P:
        pass
    p = _P()
    for k, v in papeleta_dict.items():
        setattr(p, k, v)
    db.guardar_papeleta(p, distrito)

    notificador.notificar_infraccion(papeleta_dict)

    print(f"  [VIGILANCIA-API] {numero} | {tipo} | {id_veh} | S/. {monto}")
    return papeleta_dict