# 🚀 PsychoSpace

**PsychoSpace** est un système de suivi de l’état psychologique des astronautes. Il collecte plusieurs indicateurs : sommeil, stress, fatigue, moral, isolement, motivation et charge de travail.

## 🛠️ Technologies

* 🐍 Python / FastAPI
* 🗄️ SQLite
* 🔌 ESP32
* 🤖 Ollama
* 🌐 Dashboard Web
* 📧 Notifications Email

## ⚙️ Fonctionnement

L’ESP32 transmet les données au serveur **FastAPI**, qui les valide, les enregistre dans **SQLite**, calcule un indice global et détecte les éventuelles alertes.

Les données sont ensuite analysées par **Ollama** et affichées sur le dashboard. Un rapport peut également être envoyé par email.
