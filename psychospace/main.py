from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import sqlite3
import json
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime

from ai import analyser_astronaute


# ============================================================
# CONFIGURATION
# ============================================================

app = FastAPI(title="PsychoSpace")

DATABASE = "psychospace.db"

GMAIL_USER = os.getenv(
    "PSYCHOSPACE_GMAIL_USER",
    ""
)

GMAIL_PASSWORD = os.getenv(
    "PSYCHOSPACE_GMAIL_PASSWORD",
    ""
)

REPORT_TO = os.getenv(
    "PSYCHOSPACE_REPORT_TO",
    ""
)


# ============================================================
# BASE DE DONNÉES
# ============================================================

def get_db():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS measurements (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            astronaut_id TEXT NOT NULL,

            timestamp TEXT NOT NULL,

            sleep_hours REAL NOT NULL,

            stress INTEGER NOT NULL,

            fatigue INTEGER NOT NULL,

            morale INTEGER NOT NULL,

            isolation INTEGER NOT NULL,

            motivation INTEGER NOT NULL DEFAULT 5,

            workload INTEGER NOT NULL DEFAULT 5,

            global_index REAL,

            level TEXT,

            ai_level TEXT,

            ai_response TEXT,

            ai_engine TEXT,

            email_status TEXT,

            email_error TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            astronaut_id TEXT NOT NULL,

            timestamp TEXT NOT NULL,

            reasons TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # Compatibilité avec ancienne base SQLite
    # --------------------------------------------------------

    columns = [
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(measurements)"
        ).fetchall()
    ]

    migrations = {

        "motivation":
            "ALTER TABLE measurements "
            "ADD COLUMN motivation INTEGER NOT NULL DEFAULT 5",

        "workload":
            "ALTER TABLE measurements "
            "ADD COLUMN workload INTEGER NOT NULL DEFAULT 5",

        "global_index":
            "ALTER TABLE measurements "
            "ADD COLUMN global_index REAL",

        "level":
            "ALTER TABLE measurements "
            "ADD COLUMN level TEXT",

        "ai_level":
            "ALTER TABLE measurements "
            "ADD COLUMN ai_level TEXT",

        "ai_response":
            "ALTER TABLE measurements "
            "ADD COLUMN ai_response TEXT",

        "ai_engine":
            "ALTER TABLE measurements "
            "ADD COLUMN ai_engine TEXT",

        "email_status":
            "ALTER TABLE measurements "
            "ADD COLUMN email_status TEXT",

        "email_error":
            "ALTER TABLE measurements "
            "ADD COLUMN email_error TEXT"
    }

    for column, query in migrations.items():

        if column not in columns:

            cursor.execute(query)

    connection.commit()

    connection.close()


init_database()


# ============================================================
# MODÈLE DES DONNÉES
# ============================================================

class PsychologicalData(BaseModel):

    astronaut_id: str = "AST-001"

    sleep_hours: float = Field(
        ge=0,
        le=12
    )

    stress: int = Field(
        ge=0,
        le=10
    )

    fatigue: int = Field(
        ge=0,
        le=10
    )

    morale: int = Field(
        ge=0,
        le=10
    )

    isolation: int = Field(
        ge=0,
        le=10
    )

    motivation: int = Field(
        ge=0,
        le=10
    )

    workload: int = Field(
        ge=0,
        le=10
    )


# ============================================================
# DIFFICULTÉ LIÉE AU SOMMEIL
# ============================================================

def calculate_sleep_difficulty(
    sleep_hours: float
):

    points = [
        (3.0, 10.0),
        (4.0, 8.0),
        (5.0, 6.0),
        (6.0, 4.0),
        (7.0, 2.0),
        (8.0, 0.0)
    ]

    if sleep_hours <= 3:

        return 10.0

    if sleep_hours >= 8:

        return 0.0

    for index in range(
        len(points) - 1
    ):

        low_hours, low_score = points[index]

        high_hours, high_score = points[index + 1]

        if (
            low_hours
            <= sleep_hours
            <= high_hours
        ):

            ratio = (
                sleep_hours - low_hours
            ) / (
                high_hours - low_hours
            )

            return (
                low_score
                + ratio
                * (
                    high_score
                    - low_score
                )
            )

    return 0.0


# ============================================================
# INDICE GLOBAL
# ============================================================

def calculate_global_index(
    data: PsychologicalData
):

    sleep_score = calculate_sleep_difficulty(
        data.sleep_hours
    )

    stress_score = float(
        data.stress
    )

    fatigue_score = float(
        data.fatigue
    )

    morale_score = float(
        10 - data.morale
    )

    isolation_score = float(
        data.isolation
    )

    motivation_score = float(
        10 - data.motivation
    )

    workload_score = float(
        data.workload
    )

    scores = [

        sleep_score,

        stress_score,

        fatigue_score,

        morale_score,

        isolation_score,

        motivation_score,

        workload_score
    ]

    return sum(scores) / len(scores)


# ============================================================
# ALERTES INDIVIDUELLES
# ============================================================

def analyze_data(
    data: PsychologicalData
):

    reasons = []

    if data.stress >= 8:

        reasons.append(
            "Stress élevé"
        )

    if data.fatigue >= 8:

        reasons.append(
            "Fatigue élevée"
        )

    if data.morale <= 3:

        reasons.append(
            "Moral faible"
        )

    if data.isolation >= 8:

        reasons.append(
            "Isolement social élevé"
        )

    if data.motivation <= 3:

        reasons.append(
            "Motivation faible"
        )

    if data.workload >= 8:

        reasons.append(
            "Charge de travail élevée"
        )

    return reasons


# ============================================================
# NIVEAU GLOBAL
# ============================================================

def calculate_level(
    global_index: float
):

    if global_index < 5:

        return "NORMAL"

    if global_index < 8:

        return "À CONTRÔLER"

    return "CRITIQUE"


# ============================================================
# ENVOI RAPPORT GMAIL
# ============================================================

def send_email_report(
    data,
    timestamp,
    global_index,
    level,
    reasons,
    ai_result
):

    if not GMAIL_USER:

        return (
            "NON CONFIGURÉ",
            "Adresse Gmail expéditeur absente"
        )

    if not GMAIL_PASSWORD:

        return (
            "NON CONFIGURÉ",
            "Mot de passe d'application absent"
        )

    if not REPORT_TO:

        return (
            "NON CONFIGURÉ",
            "Adresse destinataire absente"
        )

    if reasons:

        alert_text = "\n".join(
            "- " + reason
            for reason in reasons
        )

    else:

        alert_text = "Aucune alerte individuelle"

    ai_response = (
        ai_result.get("reponse")
        or "Aucune réponse IA."
    )

    ai_engine = (
        ai_result.get("ia")
        or "indisponible"
    )

    subject = (
        "PsychoSpace - Rapport "
        + data.astronaut_id
        + " - "
        + level
    )

    body = f"""
PSYCHOSPACE
HORIZON 2080
RAPPORT D'EVALUATION

----------------------------------------
IDENTIFICATION
----------------------------------------

Astronaute : {data.astronaut_id}
Date / heure : {timestamp}

----------------------------------------
MESURES
----------------------------------------

Sommeil          : {data.sleep_hours:.1f} h
Stress           : {data.stress}/10
Fatigue          : {data.fatigue}/10
Moral            : {data.morale}/10
Isolement        : {data.isolation}/10
Motivation       : {data.motivation}/10
Charge de travail: {data.workload}/10

----------------------------------------
INDICE GLOBAL
----------------------------------------

Indice : {global_index:.2f}/10

Niveau : {level}

----------------------------------------
ALERTES INDIVIDUELLES
----------------------------------------

{alert_text}

----------------------------------------
ANALYSE IA LOCALE
----------------------------------------

Moteur : {ai_engine}

{ai_response}

----------------------------------------
SYSTEME
----------------------------------------

Rapport généré automatiquement par
PsychoSpace.
"""

    message = EmailMessage()

    message["From"] = GMAIL_USER

    message["To"] = REPORT_TO

    message["Subject"] = subject

    message.set_content(body)

    try:

        with smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=30
        ) as server:

            server.starttls()

            server.login(
                GMAIL_USER,
                GMAIL_PASSWORD
            )

            server.send_message(
                message
            )

        return (
            "ENVOYÉ",
            ""
        )

    except Exception as error:

        return (
            "ERREUR",
            str(error)
        )


# ============================================================
# SAUVEGARDE MESURE
# ============================================================

def save_measurement(
    data,
    timestamp,
    global_index,
    level,
    ai_result,
    email_status,
    email_error
):

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO measurements (

            astronaut_id,

            timestamp,

            sleep_hours,

            stress,

            fatigue,

            morale,

            isolation,

            motivation,

            workload,

            global_index,

            level,

            ai_level,

            ai_response,

            ai_engine,

            email_status,

            email_error

        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
    """, (

        data.astronaut_id,

        timestamp,

        data.sleep_hours,

        data.stress,

        data.fatigue,

        data.morale,

        data.isolation,

        data.motivation,

        data.workload,

        global_index,

        level,

        level,

        ai_result.get(
            "reponse"
        ),

        ai_result.get(
            "ia"
        ),

        email_status,

        email_error
    ))

    connection.commit()

    connection.close()


# ============================================================
# SAUVEGARDE ALERTE
# ============================================================

def save_alert(
    astronaut_id,
    timestamp,
    reasons
):

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO alerts (
            astronaut_id,
            timestamp,
            reasons
        )
        VALUES (?, ?, ?)
    """, (

        astronaut_id,

        timestamp,

        " | ".join(reasons)
    ))

    connection.commit()

    connection.close()


# ============================================================
# RÉCEPTION DES DONNÉES ESP32
# ============================================================

@app.post(
    "/api/psychospace/data"
)
def receive_data(
    data: PsychologicalData
):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # --------------------------------------------------------
    # CALCUL INDICE GLOBAL
    # --------------------------------------------------------

    global_index = calculate_global_index(
        data
    )

    level = calculate_level(
        global_index
    )

    reasons = analyze_data(
        data
    )

    # --------------------------------------------------------
    # ANALYSE IA LOCALE
    # --------------------------------------------------------

    ai_result = analyser_astronaute(

        sleep_hours=data.sleep_hours,

        stress=data.stress,

        fatigue=data.fatigue,

        morale=data.morale,

        isolation=data.isolation,

        motivation=data.motivation,

        workload=data.workload,

        global_index=global_index,

        niveau=level,

        alertes=reasons
    )

    # --------------------------------------------------------
    # LE NIVEAU OFFICIEL RESTE CELUI DU CALCUL
    # --------------------------------------------------------

    ai_result["niveau"] = level

    # --------------------------------------------------------
    # ENVOI RAPPORT GMAIL
    # --------------------------------------------------------

    email_status, email_error = (
        send_email_report(

            data=data,

            timestamp=timestamp,

            global_index=global_index,

            level=level,

            reasons=reasons,

            ai_result=ai_result
        )
    )

    # --------------------------------------------------------
    # SAUVEGARDE
    # --------------------------------------------------------

    save_measurement(

        data=data,

        timestamp=timestamp,

        global_index=global_index,

        level=level,

        ai_result=ai_result,

        email_status=email_status,

        email_error=email_error
    )

    # --------------------------------------------------------
    # SAUVEGARDE ALERTES
    # --------------------------------------------------------

    if reasons:

        save_alert(

            data.astronaut_id,

            timestamp,

            reasons
        )

    # --------------------------------------------------------
    # CONSOLE
    # --------------------------------------------------------

    print()

    print(
        "==================================="
    )

    print(
        "       PSYCHOSPACE - DONNEES"
    )

    print(
        "==================================="
    )

    print(
        f"Astronaute : {data.astronaut_id}"
    )

    print(
        f"Date/heure : {timestamp}"
    )

    print(
        f"Sommeil    : {data.sleep_hours} h"
    )

    print(
        f"Stress     : {data.stress}/10"
    )

    print(
        f"Fatigue    : {data.fatigue}/10"
    )

    print(
        f"Morale     : {data.morale}/10"
    )

    print(
        f"Isolement  : {data.isolation}/10"
    )

    print(
        f"Motivation : {data.motivation}/10"
    )

    print(
        f"Travail    : {data.workload}/10"
    )

    print(
        f"Indice     : {global_index:.2f}/10"
    )

    print(
        f"Niveau     : {level}"
    )

    if reasons:

        print("⚠ ALERTES")

        for reason in reasons:

            print(
                f"  - {reason}"
            )

    else:

        print(
            "✓ Aucune alerte individuelle"
        )

    print()

    print("IA :")

    print(
        ai_result.get(
            "reponse",
            ""
        )
    )

    print()

    print(
        f"EMAIL : {email_status}"
    )

    if email_error:

        print(
            f"ERREUR EMAIL : {email_error}"
        )

    print(
        "==================================="
    )

    print()

    return {

        "status": "ok",

        "astronaut_id":
            data.astronaut_id,

        "timestamp":
            timestamp,

        "global_index":
            round(
                global_index,
                2
            ),

        "niveau":
            level,

        "alert":
            len(reasons) > 0,

        "reasons":
            reasons,

        "ai":
            ai_result,

        "email": {

            "status":
                email_status,

            "error":
                email_error
        }
    }


# ============================================================
# API : DERNIÈRE MESURE
# ============================================================

@app.get(
    "/api/psychospace/status"
)
def get_status():

    connection = get_db()
    cursor = connection.cursor()

    row = cursor.execute("""
        SELECT *
        FROM measurements
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    connection.close()

    if row is None:

        return {
            "status": "no_data"
        }

    data = PsychologicalData(

        astronaut_id=row[
            "astronaut_id"
        ],

        sleep_hours=row[
            "sleep_hours"
        ],

        stress=row[
            "stress"
        ],

        fatigue=row[
            "fatigue"
        ],

        morale=row[
            "morale"
        ],

        isolation=row[
            "isolation"
        ],

        motivation=row[
            "motivation"
        ],

        workload=row[
            "workload"
        ]
    )

    global_index = (
        row["global_index"]
    )

    if global_index is None:

        global_index = (
            calculate_global_index(
                data
            )
        )

    level = (
        row["level"]
        or calculate_level(
            global_index
        )
    )

    reasons = analyze_data(
        data
    )

    return {

        "status": "ok",

        "data":
            dict(row),

        "global_index":
            round(
                global_index,
                2
            ),

        "niveau":
            level,

        "alert":
            len(reasons) > 0,

        "reasons":
            reasons
    }


# ============================================================
# API : HISTORIQUE
# ============================================================

@app.get(
    "/api/psychospace/history"
)
def get_history():

    connection = get_db()
    cursor = connection.cursor()

    rows = cursor.execute("""
        SELECT *
        FROM measurements
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    connection.close()

    return {

        "measurements": [

            dict(row)

            for row in rows
        ]
    }


# ============================================================
# API : ALERTES
# ============================================================

@app.get(
    "/api/psychospace/alerts"
)
def get_alerts():

    connection = get_db()
    cursor = connection.cursor()

    rows = cursor.execute("""
        SELECT *
        FROM alerts
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    connection.close()

    return {

        "alerts": [

            dict(row)

            for row in rows
        ]
    }


# ============================================================
# DASHBOARD
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
def dashboard():

    connection = get_db()
    cursor = connection.cursor()

    latest = cursor.execute("""
        SELECT *
        FROM measurements
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    measurements_count = cursor.execute("""
        SELECT COUNT(*)
        FROM measurements
    """).fetchone()[0]

    alerts_count = cursor.execute("""
        SELECT COUNT(*)
        FROM alerts
    """).fetchone()[0]

    history = cursor.execute("""
        SELECT *
        FROM measurements
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    connection.close()

    # --------------------------------------------------------
    # ÉTAT PAR DÉFAUT
    # --------------------------------------------------------

    if latest is None:

        status_text = "Aucune donnée"

        status_class = "neutral"

        astronaut_id = "-"

        sleep = "-"
        stress = "-"
        fatigue = "-"
        morale = "-"
        isolation = "-"
        motivation = "-"
        workload = "-"
        global_index = "-"

        ai_level = "-"

        ai_response = (
            "Aucune analyse IA disponible."
        )

        ai_engine = "-"

        email_status = "-"

        labels = []

        stress_values = []
        fatigue_values = []
        morale_values = []
        isolation_values = []
        motivation_values = []
        workload_values = []
        global_index_values = []

    else:

        current_data = PsychologicalData(

            astronaut_id=
                latest["astronaut_id"],

            sleep_hours=
                latest["sleep_hours"],

            stress=
                latest["stress"],

            fatigue=
                latest["fatigue"],

            morale=
                latest["morale"],

            isolation=
                latest["isolation"],

            motivation=
                latest["motivation"],

            workload=
                latest["workload"]
        )

        current_index = (
            latest["global_index"]
        )

        if current_index is None:

            current_index = (
                calculate_global_index(
                    current_data
                )
            )

        current_level = (
            latest["level"]
            or calculate_level(
                current_index
            )
        )

        reasons = analyze_data(
            current_data
        )

        if current_level == "NORMAL":

            status_class = "ok"

        elif current_level == "À CONTRÔLER":

            status_class = "warning"

        else:

            status_class = "danger"

        status_text = current_level

        astronaut_id = (
            latest["astronaut_id"]
        )

        sleep = (
            f'{latest["sleep_hours"]:.1f} h'
        )

        stress = (
            f'{latest["stress"]}/10'
        )

        fatigue = (
            f'{latest["fatigue"]}/10'
        )

        morale = (
            f'{latest["morale"]}/10'
        )

        isolation = (
            f'{latest["isolation"]}/10'
        )

        motivation = (
            f'{latest["motivation"]}/10'
        )

        workload = (
            f'{latest["workload"]}/10'
        )

        global_index = (
            f"{current_index:.2f}/10"
        )

        ai_level = (
            latest["ai_level"]
            or current_level
        )

        ai_response = (
            latest["ai_response"]
            or "Aucune réponse IA disponible."
        )

        ai_engine = (
            latest["ai_engine"]
            or "indisponible"
        )

        email_status = (
            latest["email_status"]
            or "inconnu"
        )

        ordered_history = list(
            reversed(history)
        )

        labels = [

            row["timestamp"][11:19]

            for row in ordered_history
        ]

        stress_values = [

            row["stress"]

            for row in ordered_history
        ]

        fatigue_values = [

            row["fatigue"]

            for row in ordered_history
        ]

        morale_values = [

            row["morale"]

            for row in ordered_history
        ]

        isolation_values = [

            row["isolation"]

            for row in ordered_history
        ]

        motivation_values = [

            row["motivation"]

            for row in ordered_history
        ]

        workload_values = [

            row["workload"]

            for row in ordered_history
        ]

        global_index_values = [

            row["global_index"]
            if row["global_index"] is not None
            else 0

            for row in ordered_history
        ]

    # --------------------------------------------------------
    # TABLEAU HISTORIQUE
    # --------------------------------------------------------

    history_rows = ""

    for row in history:

        row_data = PsychologicalData(

            astronaut_id=
                row["astronaut_id"],

            sleep_hours=
                row["sleep_hours"],

            stress=
                row["stress"],

            fatigue=
                row["fatigue"],

            morale=
                row["morale"],

            isolation=
                row["isolation"],

            motivation=
                row["motivation"],

            workload=
                row["workload"]
        )

        row_index = row[
            "global_index"
        ]

        if row_index is None:

            row_index = (
                calculate_global_index(
                    row_data
                )
            )

        row_level = (
            row["level"]
            or calculate_level(
                row_index
            )
        )

        if row_level == "NORMAL":

            state_badge = (
                '<span class="badge ok">'
                'NORMAL'
                '</span>'
            )

        elif row_level == "À CONTRÔLER":

            state_badge = (
                '<span class="badge warning">'
                'À CONTRÔLER'
                '</span>'
            )

        else:

            state_badge = (
                '<span class="badge danger">'
                'CRITIQUE'
                '</span>'
            )

        email_value = (
            row["email_status"]
            or "inconnu"
        )

        history_rows += f"""
        <tr>

            <td>
                {row["timestamp"]}
            </td>

            <td>
                {row["astronaut_id"]}
            </td>

            <td>
                {row["sleep_hours"]:.1f} h
            </td>

            <td>
                {row["stress"]}/10
            </td>

            <td>
                {row["fatigue"]}/10
            </td>

            <td>
                {row["morale"]}/10
            </td>

            <td>
                {row["isolation"]}/10
            </td>

            <td>
                {row["motivation"]}/10
            </td>

            <td>
                {row["workload"]}/10
            </td>

            <td>
                {row_index:.2f}
            </td>

            <td>
                {state_badge}
            </td>

            <td>
                {email_value}
            </td>

        </tr>
        """

    # --------------------------------------------------------
    # DONNÉES JAVASCRIPT
    # --------------------------------------------------------

    labels_json = json.dumps(
        labels
    )

    stress_json = json.dumps(
        stress_values
    )

    fatigue_json = json.dumps(
        fatigue_values
    )

    morale_json = json.dumps(
        morale_values
    )

    isolation_json = json.dumps(
        isolation_values
    )

    motivation_json = json.dumps(
        motivation_values
    )

    workload_json = json.dumps(
        workload_values
    )

    global_index_json = json.dumps(
        global_index_values
    )

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    html = """
<!DOCTYPE html>
<html lang="fr">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>PsychoSpace - Horizon 2080</title>

<script
    src="https://cdn.jsdelivr.net/npm/chart.js">
</script>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    background: #0b1020;
    color: #f5f7ff;
}

header {
    background: #111831;
    padding: 20px;
    border-bottom: 1px solid #293252;
}

header h1 {
    margin: 0;
    font-size: 28px;
}

header p {
    margin: 6px 0 0;
    color: #9da8c7;
}

.container {
    max-width: 1500px;
    margin: auto;
    padding: 25px;
}

.topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
    margin-bottom: 25px;
    flex-wrap: wrap;
}

.button {
    display: inline-block;
    padding: 12px 18px;
    background: #283a72;
    color: white;
    text-decoration: none;
    border-radius: 8px;
    border: none;
    cursor: pointer;
    font-size: 15px;
}

.button:hover {
    background: #36509a;
}

.cards {
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(180px, 1fr));
    gap: 15px;
    margin-bottom: 25px;
}

.card {
    background: #151d38;
    border: 1px solid #293252;
    border-radius: 12px;
    padding: 20px;
}

.card-title {
    color: #9da8c7;
    font-size: 14px;
    margin-bottom: 10px;
}

.card-value {
    font-size: 28px;
    font-weight: bold;
}

.status {
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 25px;
    border: 1px solid #293252;
}

.status.ok {
    background: #10291f;
    border-color: #1d704c;
}

.status.warning {
    background: #302814;
    border-color: #806c24;
}

.status.danger {
    background: #35151a;
    border-color: #8c2e3a;
}

.status.neutral {
    background: #181d2d;
}

.status-title {
    font-size: 14px;
    color: #9da8c7;
}

.status-value {
    font-size: 30px;
    font-weight: bold;
    margin-top: 5px;
}

.section {
    background: #151d38;
    border: 1px solid #293252;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 25px;
}

.section h2 {
    margin-top: 0;
}

.index-box {
    background: #0e1428;
    border: 1px solid #293252;
    border-radius: 10px;
    padding: 18px;
    margin-bottom: 20px;
}

.index-value {
    font-size: 32px;
    font-weight: bold;
}

.index-description {
    margin-top: 8px;
    color: #9da8c7;
}

.ai-box {
    background: #0e1428;
    border: 1px solid #293252;
    border-radius: 10px;
    padding: 18px;
}

.ai-level {
    font-size: 20px;
    font-weight: bold;
    margin-bottom: 12px;
}

.ai-response {
    white-space: pre-wrap;
    line-height: 1.6;
    color: #dce2f5;
}

.ai-engine {
    margin-top: 15px;
    color: #7f8baa;
    font-size: 13px;
}

.email-status {
    margin-top: 15px;
    color: #9da8c7;
    font-size: 14px;
}

.charts {
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(350px, 1fr));
    gap: 20px;
}

.chart-container {
    position: relative;
    height: 300px;
}

.table-container {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    min-width: 1250px;
}

th,
td {
    padding: 12px;
    border-bottom: 1px solid #293252;
    text-align: left;
}

th {
    color: #9da8c7;
    font-size: 13px;
}

.badge {
    padding: 5px 9px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
}

.badge.ok {
    background: #164c36;
}

.badge.warning {
    background: #66551c;
}

.badge.danger {
    background: #702733;
}

.refresh {
    color: #687391;
    font-size: 13px;
    margin-top: 10px;
}

.footer {
    text-align: center;
    color: #687391;
    padding: 25px;
}

@media (max-width: 600px) {

    .container {
        padding: 15px;
    }

    header h1 {
        font-size: 23px;
    }

    .card-value {
        font-size: 23px;
    }

}

</style>

</head>


<body>


<header>

<h1>🛰️ PsychoSpace</h1>

<p>
Horizon 2080 — Surveillance psychologique de l'équipage
</p>

</header>


<div class="container">


<div class="topbar">

<div>

<strong>Astronaute :</strong>

<span id="astronautId">
__ASTRONAUT_ID__
</span>

</div>

<a
    class="button"
    href="/questionnaire"
>
📝 Questionnaire
</a>

</div>


<div
    id="statusBox"
    class="status __STATUS_CLASS__"
>

<div class="status-title">
ÉTAT PSYCHOLOGIQUE
</div>

<div
    id="statusValue"
    class="status-value"
>
__STATUS_TEXT__
</div>

</div>


<div class="cards">


<div class="card">

<div class="card-title">
Sommeil
</div>

<div
    id="sleepValue"
    class="card-value"
>
__SLEEP__
</div>

</div>


<div class="card">

<div class="card-title">
Stress
</div>

<div
    id="stressValue"
    class="card-value"
>
__STRESS__
</div>

</div>


<div class="card">

<div class="card-title">
Fatigue
</div>

<div
    id="fatigueValue"
    class="card-value"
>
__FATIGUE__
</div>

</div>


<div class="card">

<div class="card-title">
Moral
</div>

<div
    id="moraleValue"
    class="card-value"
>
__MORALE__
</div>

</div>


<div class="card">

<div class="card-title">
Isolement
</div>

<div
    id="isolationValue"
    class="card-value"
>
__ISOLATION__
</div>

</div>


<div class="card">

<div class="card-title">
Motivation
</div>

<div
    id="motivationValue"
    class="card-value"
>
__MOTIVATION__
</div>

</div>


<div class="card">

<div class="card-title">
Charge de travail
</div>

<div
    id="workloadValue"
    class="card-value"
>
__WORKLOAD__
</div>

</div>


<div class="card">

<div class="card-title">
Indice global
</div>

<div
    id="globalIndexValue"
    class="card-value"
>
__GLOBAL_INDEX__
</div>

</div>


<div class="card">

<div class="card-title">
Mesures enregistrées
</div>

<div
    id="measurementsCount"
    class="card-value"
>
__MEASUREMENTS_COUNT__
</div>

</div>


<div class="card">

<div class="card-title">
Alertes enregistrées
</div>

<div
    id="alertsCount"
    class="card-value"
>
__ALERTS_COUNT__
</div>

</div>


</div>


<div class="section">

<h2>📊 Indice global</h2>

<div class="index-box">

<div
    id="globalIndexMain"
    class="index-value"
>
__GLOBAL_INDEX__
</div>

<div class="index-description">
Indice moyen de difficulté psychologique sur 7 critères.
</div>

</div>

</div>


<div class="section">

<h2>🤖 Analyse IA PsychoSpace</h2>

<div class="ai-box">

<div
    id="aiLevel"
    class="ai-level"
>
__AI_LEVEL__
</div>

<div
    id="aiResponse"
    class="ai-response"
>
__AI_RESPONSE__
</div>

<div
    id="aiEngine"
    class="ai-engine"
>
IA locale : __AI_ENGINE__
</div>

<div
    id="emailStatus"
    class="email-status"
>
Rapport e-mail : __EMAIL_STATUS__
</div>

</div>

</div>


<div class="section">

<h2>📈 Évolution psychologique</h2>

<div class="charts">

<div class="chart-container">
<canvas id="stressChart"></canvas>
</div>

<div class="chart-container">
<canvas id="fatigueChart"></canvas>
</div>

<div class="chart-container">
<canvas id="moraleChart"></canvas>
</div>

<div class="chart-container">
<canvas id="isolationChart"></canvas>
</div>

<div class="chart-container">
<canvas id="motivationChart"></canvas>
</div>

<div class="chart-container">
<canvas id="workloadChart"></canvas>
</div>

<div class="chart-container">
<canvas id="globalIndexChart"></canvas>
</div>

</div>

</div>


<div class="section">

<h2>📋 Historique</h2>

<div class="refresh">
Actualisation automatique toutes les 3 secondes.
</div>

<div class="table-container">

<table>

<thead>

<tr>

<th>Date / heure</th>

<th>Astronaute</th>

<th>Sommeil</th>

<th>Stress</th>

<th>Fatigue</th>

<th>Moral</th>

<th>Isolement</th>

<th>Motivation</th>

<th>Travail</th>

<th>Indice</th>

<th>État</th>

<th>Rapport e-mail</th>

</tr>

</thead>

<tbody id="historyBody">

__HISTORY_ROWS__

</tbody>

</table>

</div>

</div>


</div>


<div class="footer">

PsychoSpace — Horizon 2080

</div>


<script>


let labels = __LABELS__;

let stressData = __STRESS_DATA__;

let fatigueData = __FATIGUE_DATA__;

let moraleData = __MORALE_DATA__;

let isolationData = __ISOLATION_DATA__;

let motivationData = __MOTIVATION_DATA__;

let workloadData = __WORKLOAD_DATA__;

let globalIndexData = __GLOBAL_INDEX_DATA__;


let stressChart = null;

let fatigueChart = null;

let moraleChart = null;

let isolationChart = null;

let motivationChart = null;

let workloadChart = null;

let globalIndexChart = null;


function createChart(
    canvasId,
    label,
    data,
    maxValue = 10
) {

    const canvas =
        document.getElementById(canvasId);

    return new Chart(
        canvas,
        {
            type: "line",

            data: {
                labels: labels,

                datasets: [
                    {
                        label: label,
                        data: data,
                        tension: 0.3,
                        fill: false
                    }
                ]
            },

            options: {
                responsive: true,

                maintainAspectRatio: false,

                scales: {
                    y: {
                        min: 0,
                        max: maxValue
                    }
                }
            }
        }
    );

}


stressChart = createChart(
    "stressChart",
    "Stress",
    stressData
);


fatigueChart = createChart(
    "fatigueChart",
    "Fatigue",
    fatigueData
);


moraleChart = createChart(
    "moraleChart",
    "Moral",
    moraleData
);


isolationChart = createChart(
    "isolationChart",
    "Isolement",
    isolationData
);


motivationChart = createChart(
    "motivationChart",
    "Motivation",
    motivationData
);


workloadChart = createChart(
    "workloadChart",
    "Charge de travail",
    workloadData
);


globalIndexChart = createChart(
    "globalIndexChart",
    "Indice global",
    globalIndexData
);


// ======================================================
// DASHBOARD
// ======================================================

async function refreshDashboard() {

    try {

        const response =
            await fetch(
                "/api/psychospace/status?t="
                + Date.now()
            );

        if (!response.ok) {

            return;
        }

        const result =
            await response.json();

        if (
            result.status !== "ok"
        ) {

            return;
        }

        const data =
            result.data;


        document.getElementById(
            "astronautId"
        ).textContent =
            data.astronaut_id;


        document.getElementById(
            "sleepValue"
        ).textContent =
            Number(
                data.sleep_hours
            ).toFixed(1)
            + " h";


        document.getElementById(
            "stressValue"
        ).textContent =
            data.stress
            + "/10";


        document.getElementById(
            "fatigueValue"
        ).textContent =
            data.fatigue
            + "/10";


        document.getElementById(
            "moraleValue"
        ).textContent =
            data.morale
            + "/10";


        document.getElementById(
            "isolationValue"
        ).textContent =
            data.isolation
            + "/10";


        document.getElementById(
            "motivationValue"
        ).textContent =
            data.motivation
            + "/10";


        document.getElementById(
            "workloadValue"
        ).textContent =
            data.workload
            + "/10";


        document.getElementById(
            "globalIndexValue"
        ).textContent =
            Number(
                result.global_index
            ).toFixed(2)
            + "/10";


        document.getElementById(
            "globalIndexMain"
        ).textContent =
            Number(
                result.global_index
            ).toFixed(2)
            + "/10";


        const statusBox =
            document.getElementById(
                "statusBox"
            );

        const statusValue =
            document.getElementById(
                "statusValue"
            );


        const level =
            result.niveau
            || "NORMAL";


        if (
            level === "NORMAL"
        ) {

            statusBox.className =
                "status ok";

        }

        else if (
            level === "À CONTRÔLER"
        ) {

            statusBox.className =
                "status warning";

        }

        else {

            statusBox.className =
                "status danger";

        }


        statusValue.textContent =
            level;


        document.getElementById(
            "aiLevel"
        ).textContent =
            data.ai_level
            || level;


        document.getElementById(
            "aiResponse"
        ).textContent =
            data.ai_response
            || "Aucune réponse IA disponible.";


        document.getElementById(
            "aiEngine"
        ).textContent =
            "IA locale : "
            + (
                data.ai_engine
                || "indisponible"
            );


        document.getElementById(
            "emailStatus"
        ).textContent =
            "Rapport e-mail : "
            + (
                data.email_status
                || "inconnu"
            );

    }

    catch (error) {

        console.error(
            "Erreur actualisation dashboard :",
            error
        );

    }

}


// ======================================================
// HISTORIQUE
// ======================================================

async function refreshHistory() {

    try {

        const response =
            await fetch(
                "/api/psychospace/history?t="
                + Date.now()
            );

        if (!response.ok) {

            return;
        }

        const result =
            await response.json();

        const tbody =
            document.getElementById(
                "historyBody"
            );

        if (!tbody) {

            return;
        }

        tbody.innerHTML = "";


        result.measurements.forEach(
            function(row) {

                let level =
                    row.level;


                if (!level) {

                    const index =
                        row.global_index
                        || 0;

                    if (index < 5) {

                        level = "NORMAL";

                    }

                    else if (index < 8) {

                        level = "À CONTRÔLER";

                    }

                    else {

                        level = "CRITIQUE";

                    }

                }


                let badgeClass =
                    "ok";


                if (
                    level === "À CONTRÔLER"
                ) {

                    badgeClass =
                        "warning";

                }

                else if (
                    level === "CRITIQUE"
                ) {

                    badgeClass =
                        "danger";

                }


                const state =
                    '<span class="badge '
                    + badgeClass
                    + '">'
                    + level
                    + "</span>";


                const tr =
                    document.createElement(
                        "tr"
                    );


                tr.innerHTML =

                    "<td>"
                    + row.timestamp
                    + "</td>"

                    + "<td>"
                    + row.astronaut_id
                    + "</td>"

                    + "<td>"
                    + Number(
                        row.sleep_hours
                    ).toFixed(1)
                    + " h"
                    + "</td>"

                    + "<td>"
                    + row.stress
                    + "/10"
                    + "</td>"

                    + "<td>"
                    + row.fatigue
                    + "/10"
                    + "</td>"

                    + "<td>"
                    + row.morale
                    + "/10"
                    + "</td>"

                    + "<td>"
                    + row.isolation
                    + "/10"
                    + "</td>"

                    + "<td>"
                    + row.motivation
                    + "/10"
                    + "</td>"

                    + "<td>"
                    + row.workload
                    + "/10"
                    + "</td>"

                    + "<td>"
                    + (
                        row.global_index != null
                        ? Number(
                            row.global_index
                          ).toFixed(2)
                        : "-"
                    )
                    + "</td>"

                    + "<td>"
                    + state
                    + "</td>"

                    + "<td>"
                    + (
                        row.email_status
                        || "inconnu"
                    )
                    + "</td>";


                tbody.appendChild(
                    tr
                );

            }
        );

    }

    catch (error) {

        console.error(
            "Erreur actualisation historique :",
            error
        );

    }

}


// ======================================================
// COMPTEURS
// ======================================================

async function refreshCounters() {

    try {

        const response =
            await fetch(
                "/api/psychospace/history?t="
                + Date.now()
            );

        if (!response.ok) {

            return;
        }

        const result =
            await response.json();

        const measurements =
            result.measurements;


        document.getElementById(
            "measurementsCount"
        ).textContent =
            measurements.length;


        let alertCount = 0;


        measurements.forEach(
            function(row) {

                const index =
                    row.global_index
                    || 0;


                if (
                    index >= 5
                    || row.stress >= 8
                    || row.fatigue >= 8
                    || row.morale <= 3
                    || row.isolation >= 8
                    || row.motivation <= 3
                    || row.workload >= 8
                ) {

                    alertCount++;

                }

            }
        );


        document.getElementById(
            "alertsCount"
        ).textContent =
            alertCount;

    }

    catch (error) {

        console.error(
            "Erreur compteurs :",
            error
        );

    }

}


// ======================================================
// GRAPHIQUES
// ======================================================

async function refreshCharts() {

    try {

        const response =
            await fetch(
                "/api/psychospace/history?t="
                + Date.now()
            );

        if (!response.ok) {

            return;
        }

        const result =
            await response.json();


        const ordered =
            result.measurements
                .slice()
                .reverse();


        const newLabels =
            ordered.map(
                function(row) {

                    return row.timestamp.substring(
                        11,
                        19
                    );

                }
            );


        const newStress =
            ordered.map(
                function(row) {

                    return row.stress;

                }
            );


        const newFatigue =
            ordered.map(
                function(row) {

                    return row.fatigue;

                }
            );


        const newMorale =
            ordered.map(
                function(row) {

                    return row.morale;

                }
            );


        const newIsolation =
            ordered.map(
                function(row) {

                    return row.isolation;

                }
            );


        const newMotivation =
            ordered.map(
                function(row) {

                    return row.motivation;

                }
            );


        const newWorkload =
            ordered.map(
                function(row) {

                    return row.workload;

                }
            );


        const newGlobalIndex =
            ordered.map(
                function(row) {

                    return row.global_index
                        != null
                        ? row.global_index
                        : 0;

                }
            );


        const charts = [

            [
                stressChart,
                newStress
            ],

            [
                fatigueChart,
                newFatigue
            ],

            [
                moraleChart,
                newMorale
            ],

            [
                isolationChart,
                newIsolation
            ],

            [
                motivationChart,
                newMotivation
            ],

            [
                workloadChart,
                newWorkload
            ],

            [
                globalIndexChart,
                newGlobalIndex
            ]
        ];


        charts.forEach(
            function(item) {

                item[0].data.labels =
                    newLabels;

                item[0].data.datasets[0].data =
                    item[1];

                item[0].update();

            }
        );

    }

    catch (error) {

        console.error(
            "Erreur graphiques :",
            error
        );

    }

}


// ======================================================
// ACTUALISATION
// ======================================================

async function refreshAll() {

    await refreshDashboard();

    await refreshHistory();

    await refreshCounters();

    await refreshCharts();

}


setInterval(
    refreshAll,
    3000
);


refreshAll();


</script>


</body>

</html>
"""

    # --------------------------------------------------------
    # REMPLACEMENT VARIABLES
    # --------------------------------------------------------

    html = html.replace(
        "__ASTRONAUT_ID__",
        str(astronaut_id)
    )

    html = html.replace(
        "__STATUS_CLASS__",
        status_class
    )

    html = html.replace(
        "__STATUS_TEXT__",
        status_text
    )

    html = html.replace(
        "__SLEEP__",
        sleep
    )

    html = html.replace(
        "__STRESS__",
        stress
    )

    html = html.replace(
        "__FATIGUE__",
        fatigue
    )

    html = html.replace(
        "__MORALE__",
        morale
    )

    html = html.replace(
        "__ISOLATION__",
        isolation
    )

    html = html.replace(
        "__MOTIVATION__",
        motivation
    )

    html = html.replace(
        "__WORKLOAD__",
        workload
    )

    html = html.replace(
        "__GLOBAL_INDEX__",
        global_index
    )

    html = html.replace(
        "__MEASUREMENTS_COUNT__",
        str(measurements_count)
    )

    html = html.replace(
        "__ALERTS_COUNT__",
        str(alerts_count)
    )

    html = html.replace(
        "__AI_LEVEL__",
        str(ai_level)
    )

    html = html.replace(
        "__AI_RESPONSE__",
        str(ai_response)
    )

    html = html.replace(
        "__AI_ENGINE__",
        str(ai_engine)
    )

    html = html.replace(
        "__EMAIL_STATUS__",
        str(email_status)
    )

    html = html.replace(
        "__HISTORY_ROWS__",
        history_rows
    )

    html = html.replace(
        "__LABELS__",
        labels_json
    )

    html = html.replace(
        "__STRESS_DATA__",
        stress_json
    )

    html = html.replace(
        "__FATIGUE_DATA__",
        fatigue_json
    )

    html = html.replace(
        "__MORALE_DATA__",
        morale_json
    )

    html = html.replace(
        "__ISOLATION_DATA__",
        isolation_json
    )

    html = html.replace(
        "__MOTIVATION_DATA__",
        motivation_json
    )

    html = html.replace(
        "__WORKLOAD_DATA__",
        workload_json
    )

    html = html.replace(
        "__GLOBAL_INDEX_DATA__",
        global_index_json
    )

    return HTMLResponse(
        content=html,
        media_type="text/html"
    )


# ============================================================
# QUESTIONNAIRE WEB
# ============================================================

@app.get(
    "/questionnaire",
    response_class=HTMLResponse
)
def questionnaire():

    html = """
<!DOCTYPE html>
<html lang="fr">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>PsychoSpace - Questionnaire</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    background: #0b1020;
    color: white;
}

.container {
    max-width: 700px;
    margin: auto;
    padding: 25px;
}

.box {
    background: #151d38;
    border: 1px solid #293252;
    border-radius: 14px;
    padding: 25px;
}

h1 {
    margin-top: 0;
}

.subtitle {
    color: #9da8c7;
    margin-bottom: 30px;
}

.field {
    margin-bottom: 25px;
}

label {
    display: block;
    margin-bottom: 10px;
    font-weight: bold;
}

input[type="number"] {
    width: 100%;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #394568;
    background: #0e1428;
    color: white;
    font-size: 16px;
}

input[type="range"] {
    width: 100%;
}

.range-value {
    font-size: 22px;
    font-weight: bold;
    margin-top: 8px;
}

button,
a {
    display: inline-block;
    padding: 13px 18px;
    border-radius: 8px;
    border: none;
    font-size: 15px;
    text-decoration: none;
    cursor: pointer;
}

button {
    background: #36509a;
    color: white;
}

a {
    background: #293252;
    color: white;
    margin-left: 8px;
}

#result {
    margin-top: 20px;
    padding: 15px;
    border-radius: 8px;
    display: none;
}

.success {
    background: #164c36;
}

.warning {
    background: #66551c;
}

.error {
    background: #702733;
}

</style>

</head>


<body>


<div class="container">

<div class="box">

<h1>📝 Questionnaire PsychoSpace</h1>

<p class="subtitle">
Évaluation quotidienne de l'état de l'astronaute.
</p>


<form id="questionnaireForm">


<div class="field">

<label for="astronaut_id">
Astronaute
</label>

<input
    id="astronaut_id"
    type="number"
    min="1"
    max="99"
    value="1"
    required
>

</div>


<div class="field">

<label for="sleep_hours">
Heures de sommeil
</label>

<input
    id="sleep_hours"
    type="number"
    min="0"
    max="12"
    step="0.5"
    value="7"
    required
>

</div>


<div class="field">

<label for="stress">
Stress
</label>

<input
    id="stress"
    type="range"
    min="0"
    max="10"
    value="3"
>

<div class="range-value">
<span id="stressValue">3</span>/10
</div>

</div>


<div class="field">

<label for="fatigue">
Fatigue
</label>

<input
    id="fatigue"
    type="range"
    min="0"
    max="10"
    value="3"
>

<div class="range-value">
<span id="fatigueValue">3</span>/10
</div>

</div>


<div class="field">

<label for="morale">
Moral
</label>

<input
    id="morale"
    type="range"
    min="0"
    max="10"
    value="7"
>

<div class="range-value">
<span id="moraleValue">7</span>/10
</div>

</div>


<div class="field">

<label for="isolation">
Isolement social
</label>

<input
    id="isolation"
    type="range"
    min="0"
    max="10"
    value="2"
>

<div class="range-value">
<span id="isolationValue">2</span>/10
</div>

</div>


<div class="field">

<label for="motivation">
Motivation
</label>

<input
    id="motivation"
    type="range"
    min="0"
    max="10"
    value="7"
>

<div class="range-value">
<span id="motivationValue">7</span>/10
</div>

</div>


<div class="field">

<label for="workload">
Charge de travail
</label>

<input
    id="workload"
    type="range"
    min="0"
    max="10"
    value="3"
>

<div class="range-value">
<span id="workloadValue">3</span>/10
</div>

</div>


<button type="submit">
Envoyer l'évaluation
</button>

<a href="/">
Retour
</a>


</form>


<div id="result"></div>


</div>

</div>


<script>


function updateValue(
    inputId,
    valueId
) {

    const input =
        document.getElementById(
            inputId
        );

    const value =
        document.getElementById(
            valueId
        );

    input.addEventListener(
        "input",
        function() {

            value.textContent =
                input.value;

        }
    );

}


updateValue(
    "stress",
    "stressValue"
);


updateValue(
    "fatigue",
    "fatigueValue"
);


updateValue(
    "morale",
    "moraleValue"
);


updateValue(
    "isolation",
    "isolationValue"
);


updateValue(
    "motivation",
    "motivationValue"
);


updateValue(
    "workload",
    "workloadValue"
);


document
    .getElementById(
        "questionnaireForm"
    )
    .addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();


            const id =
                parseInt(
                    document.getElementById(
                        "astronaut_id"
                    ).value
                );


            const data = {

                astronaut_id:
                    id < 10
                    ? "AST-0" + id
                    : "AST-" + id,

                sleep_hours:
                    parseFloat(
                        document.getElementById(
                            "sleep_hours"
                        ).value
                    ),

                stress:
                    parseInt(
                        document.getElementById(
                            "stress"
                        ).value
                    ),

                fatigue:
                    parseInt(
                        document.getElementById(
                            "fatigue"
                        ).value
                    ),

                morale:
                    parseInt(
                        document.getElementById(
                            "morale"
                        ).value
                    ),

                isolation:
                    parseInt(
                        document.getElementById(
                            "isolation"
                        ).value
                    ),

                motivation:
                    parseInt(
                        document.getElementById(
                            "motivation"
                        ).value
                    ),

                workload:
                    parseInt(
                        document.getElementById(
                            "workload"
                        ).value
                    )
            };


            const result =
                document.getElementById(
                    "result"
                );


            result.style.display =
                "block";

            result.className =
                "success";

            result.textContent =
                "Envoi en cours...";


            try {

                const response =
                    await fetch(
                        "/api/psychospace/data",
                        {

                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify(
                                    data
                                )
                        }
                    );


                const responseData =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        "Erreur serveur"
                    );

                }


                const email =
                    responseData.email;


                let message =
                    "✓ Évaluation enregistrée."
                    + "<br>"
                    + "Indice global : "
                    + Number(
                        responseData.global_index
                    ).toFixed(2)
                    + "/10"
                    + "<br>"
                    + "Niveau : "
                    + responseData.niveau;


                if (email) {

                    message +=
                        "<br>"
                        + "Rapport e-mail : "
                        + email.status;

                }


                if (
                    responseData.niveau
                    === "CRITIQUE"
                ) {

                    result.className =
                        "error";

                }

                else if (
                    responseData.niveau
                    === "À CONTRÔLER"
                ) {

                    result.className =
                        "warning";

                }

                else {

                    result.className =
                        "success";

                }


                if (
                    responseData.reasons
                    &&
                    responseData.reasons.length
                    > 0
                ) {

                    message +=
                        "<br><br>"
                        + "<strong>Alertes :</strong>"
                        + "<br>"
                        + responseData.reasons.join(
                            "<br>"
                        );

                }


                result.innerHTML =
                    message;

            }

            catch (error) {

                result.className =
                    "error";

                result.textContent =
                    "Erreur lors de l'envoi des données.";

                console.error(
                    error
                );

            }

        }
    );


</script>


</body>

</html>
"""

    return HTMLResponse(
        content=html,
        media_type="text/html"
    )


# ============================================================
# TEST
# ============================================================

@app.get("/api/test")
def test_api():

    return {

        "project":
            "PsychoSpace",

        "status":
            "online",

        "system":
            "Horizon 2080",

        "criteria":
            7,

        "ai":
            "Ollama / llama3.2:3b",

        "email": {

            "sender":
                GMAIL_USER,

            "recipient":
                REPORT_TO,

            "configured":
                bool(
                    GMAIL_USER
                    and GMAIL_PASSWORD
                    and REPORT_TO
                )
        }
    }
