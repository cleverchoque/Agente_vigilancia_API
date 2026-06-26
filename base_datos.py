# -*- coding: utf-8 -*-
"""
=============================================================
  BASE DE DATOS - AGENTE DE VIGILANCIA
  Sistema Multi-Agente de Transito - FINESI UNAP
=============================================================
  Motor: SQLite (incluido en Python, sin instalar nada)
  Archivo generado: vigilancia.db

  Tablas:
    - papeletas    : infracciones emitidas
    - vehiculos    : registro de vehiculos del sistema
    - eventos      : log de eventos del agente
=============================================================
"""

import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "vigilancia.db")


# -----------------------------------------------
#  CONEXION Y CREACION DE TABLAS
# -----------------------------------------------

def conectar():
    """Retorna una conexion a la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # resultados como diccionarios
    return conn


def inicializar():
    """Crea las tablas si no existen. Llamar una sola vez al inicio."""
    conn = conectar()
    cur  = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS papeletas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            numero      TEXT    NOT NULL UNIQUE,
            timestamp   TEXT    NOT NULL,
            id_veh      TEXT    NOT NULL,
            nodo        TEXT    NOT NULL,
            tipo        TEXT    NOT NULL,
            detalle     TEXT,
            vel_kmh     REAL,
            peso_tn     REAL,
            monto_s     REAL,
            distrito    TEXT    DEFAULT 'centro'
        );

        CREATE TABLE IF NOT EXISTS vehiculos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            id_veh      TEXT    NOT NULL UNIQUE,
            peso_tn     REAL    DEFAULT 1.0,
            autorizado  INTEGER DEFAULT 1,
            propietario TEXT    DEFAULT 'Desconocido',
            registrado  TEXT    NOT NULL,
            actualizado TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS eventos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            tipo        TEXT    NOT NULL,
            mensaje     TEXT    NOT NULL,
            id_veh      TEXT,
            distrito    TEXT    DEFAULT 'centro'
        );
    """)

    conn.commit()
    conn.close()
    print(f"  [DB] Base de datos lista: {DB_PATH}")


# -----------------------------------------------
#  PAPELETAS
# -----------------------------------------------

def guardar_papeleta(papeleta, distrito="centro"):
    """Guarda una papeleta en la base de datos."""
    conn = conectar()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO papeletas
            (numero, timestamp, id_veh, nodo, tipo, detalle, vel_kmh, peso_tn, monto_s, distrito)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            papeleta.numero,
            papeleta.timestamp,
            papeleta.id_veh,
            papeleta.nodo,
            papeleta.tipo,
            papeleta.detalle,
            papeleta.vel_kmh,
            papeleta.peso_tn,
            papeleta.monto_s,
            distrito,
        ))
        conn.commit()
    finally:
        conn.close()


def obtener_papeletas(id_veh=None, distrito=None, limite=50):
    """
    Retorna lista de papeletas.
    Filtros opcionales: por vehiculo o por distrito.
    """
    conn = conectar()
    try:
        condiciones = []
        params      = []
        if id_veh:
            condiciones.append("id_veh = ?")
            params.append(id_veh)
        if distrito:
            condiciones.append("distrito = ?")
            params.append(distrito)

        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
        params.append(limite)

        cur = conn.execute(
            f"SELECT * FROM papeletas {where} ORDER BY id DESC LIMIT ?",
            params
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def total_multas(id_veh=None):
    """Retorna el total de multas acumuladas en soles."""
    conn = conectar()
    try:
        if id_veh:
            cur = conn.execute(
                "SELECT COALESCE(SUM(monto_s), 0) FROM papeletas WHERE id_veh = ?",
                (id_veh,)
            )
        else:
            cur = conn.execute(
                "SELECT COALESCE(SUM(monto_s), 0) FROM papeletas"
            )
        return cur.fetchone()[0]
    finally:
        conn.close()


# -----------------------------------------------
#  VEHICULOS
# -----------------------------------------------

def registrar_vehiculo(id_veh, peso_tn=1.0, autorizado=True, propietario="Desconocido"):
    """
    Registra un vehiculo nuevo o actualiza si ya existe.
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn  = conectar()
    try:
        conn.execute("""
            INSERT INTO vehiculos (id_veh, peso_tn, autorizado, propietario, registrado, actualizado)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_veh) DO UPDATE SET
                peso_tn     = excluded.peso_tn,
                autorizado  = excluded.autorizado,
                propietario = excluded.propietario,
                actualizado = excluded.actualizado
        """, (id_veh, peso_tn, int(autorizado), propietario, ahora, ahora))
        conn.commit()
    finally:
        conn.close()


def obtener_vehiculo(id_veh):
    """
    Retorna los datos de un vehiculo o None si no existe.
    """
    conn = conectar()
    try:
        cur = conn.execute(
            "SELECT * FROM vehiculos WHERE id_veh = ?", (id_veh,)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def obtener_todos_vehiculos():
    """Retorna todos los vehiculos registrados."""
    conn = conectar()
    try:
        cur = conn.execute("SELECT * FROM vehiculos ORDER BY id_veh")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# -----------------------------------------------
#  EVENTOS / LOG
# -----------------------------------------------

def guardar_evento(tipo, mensaje, id_veh=None, distrito="centro"):
    """Guarda una entrada de log en la base de datos."""
    conn = conectar()
    try:
        conn.execute("""
            INSERT INTO eventos (timestamp, tipo, mensaje, id_veh, distrito)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            tipo,
            mensaje,
            id_veh,
            distrito,
        ))
        conn.commit()
    finally:
        conn.close()


def obtener_eventos(limite=20):
    """Retorna los ultimos eventos del log."""
    conn = conectar()
    try:
        cur = conn.execute(
            "SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limite,)
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# -----------------------------------------------
#  REPORTES
# -----------------------------------------------

def reporte_por_vehiculo():
    """
    Retorna un resumen de infracciones agrupado por vehiculo.
    """
    conn = conectar()
    try:
        cur = conn.execute("""
            SELECT
                id_veh,
                COUNT(*)        AS total_papeletas,
                SUM(monto_s)    AS total_monto_s,
                MAX(timestamp)  AS ultima_infraccion
            FROM papeletas
            GROUP BY id_veh
            ORDER BY total_monto_s DESC
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def reporte_por_tipo():
    """
    Retorna un resumen de infracciones agrupado por tipo.
    """
    conn = conectar()
    try:
        cur = conn.execute("""
            SELECT
                tipo,
                COUNT(*)     AS total,
                SUM(monto_s) AS monto_total_s
            FROM papeletas
            GROUP BY tipo
            ORDER BY total DESC
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def reporte_por_distrito():
    """
    Retorna un resumen de infracciones agrupado por distrito.
    """
    conn = conectar()
    try:
        cur = conn.execute("""
            SELECT
                distrito,
                COUNT(*)     AS total,
                SUM(monto_s) AS monto_total_s
            FROM papeletas
            GROUP BY distrito
            ORDER BY total DESC
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def imprimir_reporte_completo():
    """Imprime un reporte completo en consola."""
    sep = "=" * 56
    print(sep)
    print("  REPORTE COMPLETO - AGENTE DE VIGILANCIA")
    print(sep)

    print("\n  Por vehiculo:")
    for r in reporte_por_vehiculo():
        print(f"    {r['id_veh']:<8} | {r['total_papeletas']} papeletas | S/. {r['total_monto_s']:.2f}")

    print("\n  Por tipo de infraccion:")
    for r in reporte_por_tipo():
        print(f"    {r['tipo']:<35} | {r['total']} veces | S/. {r['monto_total_s']:.2f}")

    print("\n  Por distrito:")
    for r in reporte_por_distrito():
        print(f"    {r['distrito']:<10} | {r['total']} infracciones | S/. {r['monto_total_s']:.2f}")

    print(f"\n  TOTAL RECAUDADO: S/. {total_multas():.2f}")
    print(sep)
