# -*- coding: utf-8 -*-
"""
=============================================================
  NOTIFICADOR
  Envia avisos a otros agentes (centro de control, vehiculos)
  cuando vigilancia detecta una infraccion o colision.
=============================================================
  Funciona por suscripcion: cada agente que quiera recibir
  avisos llama a /api/vigilancia/suscribir con su propia URL
  de webhook. Cuando ocurre un evento, vigilancia envia un
  mensaje FORMAL en formato FIPA-ACL (estandar de la materia
  Tecnologias Emergentes - Protocolos de Comunicacion entre
  Agentes) a todas las URLs suscritas.

  Performativa usada: INFORM
  (Vigilancia informa un hecho ya ocurrido, no negocia nada
  en este punto, por eso INFORM es la performativa correcta
  segun el estandar FIPA, a diferencia de REQUEST o CFP que
  si esperan una respuesta o negociacion).

  Si un agente no tiene servidor propio (todavia no subio su
  API), simplemente no se suscribe y no recibe nada, pero
  vigilancia sigue funcionando igual sin fallar.
=============================================================
"""

import requests
from fipa_acl import inform_papeleta, inform_colision, MensajeACL, Performativa


# Suscriptores en memoria: {"centro_control": "https://...", "vehiculos": "https://..."}
SUSCRIPTORES = {}

# Historial de conversaciones ACL enviadas (para trazabilidad academica)
HISTORIAL_ACL = []
MAX_HISTORIAL = 100


def suscribir(nombre_agente, url_webhook):
    """Registra la URL de webhook de un agente."""
    SUSCRIPTORES[nombre_agente] = url_webhook
    print(f"  [NOTIFICADOR] Suscrito: {nombre_agente} -> {url_webhook}")


def desuscribir(nombre_agente):
    """Quita un agente de la lista de notificaciones."""
    SUSCRIPTORES.pop(nombre_agente, None)
    print(f"  [NOTIFICADOR] Desuscrito: {nombre_agente}")


def listar_suscriptores():
    """Retorna los agentes suscritos actualmente."""
    return dict(SUSCRIPTORES)


def obtener_historial_acl(limite=20):
    """Retorna los ultimos mensajes ACL enviados (para depurar/sustentar)."""
    return HISTORIAL_ACL[-limite:]


def notificar_infraccion(papeleta_dict):
    """
    INFORM: Vigilancia informa a cada suscriptor que se emitio
    una papeleta. Se construye UN mensaje ACL por destinatario,
    porque en FIPA cada conversacion es 1 a 1 (aunque el
    'receiver' pueda anotarse como grupo si se desea).
    """
    for nombre_agente, url in SUSCRIPTORES.items():
        msg = inform_papeleta(papeleta_dict, receiver=nombre_agente)
        _enviar_mensaje_acl(nombre_agente, url, msg)


def notificar_colision(colision_dict):
    """
    INFORM: Vigilancia informa sobre una colision detectada.
    """
    for nombre_agente, url in SUSCRIPTORES.items():
        msg = inform_colision(colision_dict, receiver=nombre_agente)
        _enviar_mensaje_acl(nombre_agente, url, msg)


def notificar_riesgo(riesgo_dict):
    """
    INFORM: Vigilancia informa sobre riesgo de colision
    (vehiculos muy cerca, sin llegar a chocar).
    """
    for nombre_agente, url in SUSCRIPTORES.items():
        msg = MensajeACL(
            performative = Performativa.INFORM,
            sender       = "AgenteVigilancia",
            receiver     = nombre_agente,
            content      = {
                "tipo_evento": "RIESGO_COLISION",
                "riesgo":      riesgo_dict,
            },
        )
        _enviar_mensaje_acl(nombre_agente, url, msg)


def _enviar_mensaje_acl(nombre_agente: str, url: str, msg: MensajeACL):
    """
    Envia un MensajeACL como payload HTTP POST.
    Usa timeout corto para no bloquear el flujo del agente
    si algun servicio esta caido o dormido (Render free tier).
    Registra cada envio en el historial para trazabilidad.
    """
    payload = msg.to_dict()

    entrada_historial = {
        "destino": nombre_agente,
        "mensaje": payload,
        "resultado": None,
    }

    if not SUSCRIPTORES:
        print(f"  [NOTIFICADOR] Sin suscriptores, mensaje ACL no se envia")
        return

    try:
        r = requests.post(url, json=payload, timeout=5)
        entrada_historial["resultado"] = r.status_code
        print(f"  [NOTIFICADOR-ACL] {msg.performative.value if hasattr(msg.performative,'value') else msg.performative} "
              f"-> {nombre_agente} ({url}): HTTP {r.status_code} | conv:{msg.conversation_id}")
    except requests.exceptions.RequestException as e:
        entrada_historial["resultado"] = f"ERROR: {e}"
        print(f"  [NOTIFICADOR-ACL] {msg.performative.value if hasattr(msg.performative,'value') else msg.performative} "
              f"-> {nombre_agente} ({url}): FALLO ({e}) | conv:{msg.conversation_id}")

    HISTORIAL_ACL.append(entrada_historial)
    if len(HISTORIAL_ACL) > MAX_HISTORIAL:
        HISTORIAL_ACL.pop(0)