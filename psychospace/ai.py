import requests


# ============================================================
# CONFIGURATION OLLAMA
# ============================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

MODEL = "llama3.2:3b"

# Le modèle peut prendre quelques secondes à démarrer
# lorsqu'il n'est pas encore chargé en mémoire.
TIMEOUT = 90


# ============================================================
# ANALYSE IA
# ============================================================

def analyser_astronaute(
    sleep_hours,
    stress,
    fatigue,
    morale,
    isolation,
    motivation,
    workload,
    global_index,
    niveau,
    alertes
):
    """
    Analyse les données psychologiques avec une IA locale Ollama.

    IMPORTANT :
    - L'indice global est calculé par PsychoSpace.
    - Le niveau est calculé par PsychoSpace.
    - L'IA ne doit jamais modifier ces valeurs.
    - L'IA ne pose aucun diagnostic médical.
    """

    if alertes:
        alertes_text = ", ".join(alertes)
    else:
        alertes_text = "Aucune alerte individuelle"

    prompt = f"""
Tu es l'assistant psychologique local de PsychoSpace,
un système de suivi d'astronautes en mission spatiale.

Analyse les données suivantes :

Astronaute : données confidentielles
Sommeil : {sleep_hours} h
Stress : {stress}/10
Fatigue : {fatigue}/10
Moral : {morale}/10
Isolement social : {isolation}/10
Motivation : {motivation}/10
Charge de travail : {workload}/10

Indice global PsychoSpace : {global_index:.2f}/10
Niveau officiel PsychoSpace : {niveau}

Alertes individuelles :
{alertes_text}

RÈGLES IMPORTANTES :

1. L'indice global est déjà calculé par PsychoSpace.
2. Le niveau officiel est déjà calculé par PsychoSpace.
3. Tu ne dois jamais modifier ou contester le niveau officiel.
4. Ne pose aucun diagnostic médical ou psychologique.
5. Ne prétends pas connaître l'état réel de l'astronaute.
6. Base-toi uniquement sur les données fournies.
7. Si une difficulté est détectée, explique-la simplement.
8. Propose au maximum 2 actions concrètes et simples.
9. Si tout va bien, indique simplement que les paramètres sont stables.
10. Réponds uniquement en français.
11. Réponse courte : maximum 5 phrases.
12. Ne répète pas toutes les valeurs numériques.

Structure souhaitée :

État :
[une courte phrase]

Observation :
[une courte phrase]

Action :
[0 à 2 actions simples si nécessaire]

Réponds directement, sans introduction supplémentaire.
"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 150
        }
    }

    try:

        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        result = response.json()

        ai_response = result.get(
            "response",
            ""
        ).strip()

        if not ai_response:

            ai_response = (
                "L'IA locale n'a retourné aucune réponse."
            )

        return {
            "niveau": niveau,
            "reponse": ai_response,
            "ia": f"Ollama / {MODEL}"
        }

    except requests.exceptions.ConnectTimeout:

        return {
            "niveau": niveau,
            "reponse": (
                "IA locale indisponible : "
                "connexion à Ollama trop longue."
            ),
            "ia": f"Ollama / {MODEL}"
        }

    except requests.exceptions.ReadTimeout:

        return {
            "niveau": niveau,
            "reponse": (
                "IA locale indisponible : "
                "délai de réponse dépassé."
            ),
            "ia": f"Ollama / {MODEL}"
        }

    except requests.exceptions.ConnectionError:

        return {
            "niveau": niveau,
            "reponse": (
                "IA locale indisponible : "
                "Ollama n'est pas accessible."
            ),
            "ia": f"Ollama / {MODEL}"
        }

    except requests.exceptions.RequestException as error:

        return {
            "niveau": niveau,
            "reponse": (
                "IA locale indisponible : "
                f"erreur de communication avec Ollama."
            ),
            "ia": f"Ollama / {MODEL}"
        }

    except Exception as error:

        return {
            "niveau": niveau,
            "reponse": (
                "IA locale indisponible : "
                "erreur inattendue."
            ),
            "ia": f"Ollama / {MODEL}"
        }
