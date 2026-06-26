# -*- coding: utf-8 -*-
"""
=============================================================
  FIPA-ACL (Agent Communication Language)
  Modulo de comunicacion formal entre agentes
=============================================================
  Implementa la estructura de mensajes FIPA-ACL para que el
  Agente de Vigilancia se comunique con los demas agentes
  del sistema (Vehiculos, Centro de Control) usando un
  protocolo estandar reconocido en sistemas multiagente.

  Referencia: FIPA (Foundation for Intelligent Physical Agents)
  Estandar academico usado en SMA.

  Campos de un mensaje ACL:
    performative    -> tipo de accion comunicativa
    sender          -> agente emisor
    receiver        -> agente receptor
    content         -> contenido del mensaje
    language        -> lenguaje utilizado (JSON en nuestro caso)
    ontology        -> dominio del conocimiento
    conversation_id -> identificador de conversacion
=============================================================
"""

import uuid
from datetime import datetime
from enum import Enum


# -----------------------------------------------
#  PERFORMATIVAS (segun el estandar FIPA-ACL)
# -----------------------------------------------

class Performativa(str, Enum):
    INFORM           = "INFORM"            # Informar un hecho (ej: papeleta emitida)
    REQUEST          = "REQUEST"           # Solicitar una accion
    QUERY_IF         = "QUERY_IF"          # Preguntar si algo es verdadero
    QUERY_REF        = "QUERY_REF"         # Pedir un dato especifico
    AGREE            = "AGREE"             # Aceptar una solicitud
    REFUSE           = "REFUSE"            # Rechazar una solicitud
    PROPOSE          = "PROPOSE"           # Hacer una propuesta
    ACCEPT_PROPOSAL  = "ACCEPT_PROPOSAL"   # Aceptar una propuesta
    REJECT_PROPOSAL  = "REJECT_PROPOSAL"   # Rechazar una propuesta
    CFP              = "CFP"               # Call For Proposal
    FAILURE          = "FAILURE"           # Informar un fallo


ONTOLOGIA_TRANSITO = "ontologia-transito-mas"
LENGUAJE_CONTENIDO  = "JSON"


# -----------------------------------------------
#  MENSAJE ACL
# -----------------------------------------------

class MensajeACL:
    """
    Representa un mensaje formal segun el estandar FIPA-ACL.

    Uso:
        msg = MensajeACL(
            performative = Performativa.INFORM,
            sender       = "AgenteVigilancia",
            receiver     = "AgenteCentroControl",
            content      = {"papeleta": "PAP-0001", "monto": 200.0},
        )
        payload = msg.to_dict()   # listo para enviar por HTTP
    """

    def __init__(self, performative: Performativa, sender: str, receiver: str,
                 content: dict, conversation_id: str = None,
                 ontology: str = ONTOLOGIA_TRANSITO,
                 language: str = LENGUAJE_CONTENIDO,
                 in_reply_to: str = None):
        self.performative     = performative
        self.sender           = sender
        self.receiver         = receiver
        self.content          = content
        self.ontology         = ontology
        self.language         = language
        self.conversation_id  = conversation_id or str(uuid.uuid4())[:12]
        self.in_reply_to      = in_reply_to
        self.timestamp        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        """Convierte el mensaje a diccionario, listo para JSON."""
        return {
            "performative":     self.performative.value if isinstance(self.performative, Performativa) else self.performative,
            "sender":           self.sender,
            "receiver":         self.receiver,
            "content":          self.content,
            "language":         self.language,
            "ontology":         self.ontology,
            "conversation_id":  self.conversation_id,
            "in_reply_to":      self.in_reply_to,
            "timestamp":        self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MensajeACL":
        """Reconstruye un MensajeACL a partir de un diccionario recibido."""
        return cls(
            performative     = data.get("performative"),
            sender           = data.get("sender"),
            receiver         = data.get("receiver"),
            content          = data.get("content", {}),
            conversation_id  = data.get("conversation_id"),
            ontology         = data.get("ontology", ONTOLOGIA_TRANSITO),
            language         = data.get("language", LENGUAJE_CONTENIDO),
            in_reply_to      = data.get("in_reply_to"),
        )

    def crear_respuesta(self, performative: Performativa, content: dict) -> "MensajeACL":
        """
        Crea un mensaje de respuesta a este mensaje, manteniendo
        la misma conversacion (conversation_id) e invirtiendo
        sender/receiver, tal como exige el protocolo FIPA.
        """
        return MensajeACL(
            performative     = performative,
            sender           = self.receiver,
            receiver         = self.sender,
            content          = content,
            conversation_id  = self.conversation_id,
            ontology         = self.ontology,
            language         = self.language,
            in_reply_to      = self.performative.value if isinstance(self.performative, Performativa) else self.performative,
        )

    def __repr__(self):
        perf = self.performative.value if isinstance(self.performative, Performativa) else self.performative
        return f"ACL({perf} | {self.sender} -> {self.receiver} | conv:{self.conversation_id})"


# -----------------------------------------------
#  CONSTRUCTORES RAPIDOS PARA CASOS COMUNES
#  DEL AGENTE DE VIGILANCIA
# -----------------------------------------------

def inform_papeleta(papeleta_dict: dict, receiver: str = "AgenteCentroControl") -> MensajeACL:
    """
    INFORM: Vigilancia informa al Centro de Control que se
    emitio una papeleta. Esta es la performativa correcta
    porque solo se esta informando un hecho, no se espera
    una negociacion.
    """
    return MensajeACL(
        performative = Performativa.INFORM,
        sender       = "AgenteVigilancia",
        receiver     = receiver,
        content      = {
            "tipo_evento": "PAPELETA_EMITIDA",
            "papeleta":    papeleta_dict,
        },
    )


def inform_colision(colision_dict: dict, receiver: str = "AgenteCentroControl") -> MensajeACL:
    """
    INFORM: Vigilancia informa sobre una colision detectada.
    """
    return MensajeACL(
        performative = Performativa.INFORM,
        sender       = "AgenteVigilancia",
        receiver     = receiver,
        content      = {
            "tipo_evento": "COLISION_DETECTADA",
            "colision":    colision_dict,
        },
    )


def request_estado_semaforo(nodo: str, receiver: str = "AgenteSemaforo") -> MensajeACL:
    """
    REQUEST: Vigilancia solicita al Agente Semaforo el estado
    actual de un semaforo especifico, para poder evaluar si
    un vehiculo cometio una infraccion.
    """
    return MensajeACL(
        performative = Performativa.REQUEST,
        sender       = "AgenteVigilancia",
        receiver     = receiver,
        content      = {
            "accion": "OBTENER_ESTADO_SEMAFORO",
            "nodo":   nodo,
        },
    )


def query_ref_datos_vehiculo(id_veh: str, receiver: str = "AgenteVehiculo") -> MensajeACL:
    """
    QUERY_REF: Vigilancia pide datos especificos de un vehiculo
    (peso, autorizacion) al Agente de Vehiculos.
    """
    return MensajeACL(
        performative = Performativa.QUERY_REF,
        sender       = "AgenteVigilancia",
        receiver     = receiver,
        content      = {
            "dato_solicitado": "datos_vehiculo",
            "id_veh":          id_veh,
        },
    )


def cfp_atencion_emergencia(colision_dict: dict, candidatos: list) -> MensajeACL:
    """
    CFP (Call For Proposal): Vigilancia detecta una colision
    grave y convoca a los agentes de respuesta disponibles
    (ej: unidades de Centro de Control) a proponer su tiempo
    de respuesta, siguiendo el Contract Net Protocol.

    'candidatos' es la lista de agentes a quienes se les
    enviara este CFP (ej: ["UnidadControl_1", "UnidadControl_2"])
    """
    return MensajeACL(
        performative = Performativa.CFP,
        sender       = "AgenteVigilancia",
        receiver     = ",".join(candidatos),
        content      = {
            "tarea":    "ATENDER_COLISION",
            "colision": colision_dict,
            "candidatos": candidatos,
        },
    )


def failure_inspeccion(id_veh: str, motivo: str, receiver: str = "AgenteCentroControl") -> MensajeACL:
    """
    FAILURE: Vigilancia informa que no pudo completar una
    inspeccion (ej: datos invalidos del vehiculo).
    """
    return MensajeACL(
        performative = Performativa.FAILURE,
        sender       = "AgenteVigilancia",
        receiver     = receiver,
        content      = {
            "accion_fallida": "INSPECCIONAR_VEHICULO",
            "id_veh":         id_veh,
            "motivo":         motivo,
        },
    )
