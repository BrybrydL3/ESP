#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ======================================================
// LCD
// ======================================================

LiquidCrystal_I2C lcd(0x27, 16, 2);

// ======================================================
// WIFI / SERVEUR
// ======================================================

const char* WIFI_SSID = "Galaxy S22+2B91";
const char* WIFI_PASSWORD = "192837465";

const char* SERVER_URL =
    "http://10.12.51.39:8000/api/psychospace/data";

// ======================================================
// JOYSTICK
// ======================================================

const int JOY_Y = 35;
const int JOY_SW = 27;

const int JOY_CENTER_Y = 1880;
const int DEAD_ZONE = 500;

const unsigned long ACTION_DELAY = 300;

// ======================================================
// BUZZER
// ======================================================

const int BUZZER = 14;

// ======================================================
// QUESTIONNAIRE
// ======================================================

// 7 critères :
// 0 = Sommeil
// 1 = Stress
// 2 = Fatigue
// 3 = Moral
// 4 = Isolement social
// 5 = Motivation
// 6 = Charge de travail

const int TOTAL_QUESTIONS = 7;

int astronautID = 1;

float sleepHours = 7.0;

// Les 6 critères sur 10
int answers[TOTAL_QUESTIONS];

int currentQuestion = 0;
int currentValue = 5;

// ======================================================
// ETATS
// ======================================================

enum State
{
    SELECT_ID,
    QUESTIONNAIRE,
    RESULT,
    SENDING
};

State state = SELECT_ID;

// ======================================================
// TEMPORISATION
// ======================================================

unsigned long lastAction = 0;

// ======================================================
// BUZZER
// ======================================================

void setupBuzzer()
{
    pinMode(BUZZER, OUTPUT);
    digitalWrite(BUZZER, LOW);
}

// ======================================================
// 1 BIP
// ======================================================

void signalOK()
{
    digitalWrite(BUZZER, HIGH);
    delay(200);
    digitalWrite(BUZZER, LOW);
}

// ======================================================
// 3 BIPS
// ======================================================

void signalAttention()
{
    for (int i = 0; i < 3; i++)
    {
        digitalWrite(BUZZER, HIGH);
        delay(250);

        digitalWrite(BUZZER, LOW);
        delay(250);
    }
}

// ======================================================
// 5 BIPS
// ======================================================

void signalAttentionForte()
{
    for (int i = 0; i < 5; i++)
    {
        digitalWrite(BUZZER, HIGH);
        delay(250);

        digitalWrite(BUZZER, LOW);
        delay(250);
    }
}

// ======================================================
// CONNEXION WIFI
// ======================================================

void connectWiFi()
{
    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("Connexion WiFi");

    Serial.println();
    Serial.println("Connexion au WiFi...");

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;

    while (
        WiFi.status() != WL_CONNECTED &&
        attempts < 30
    )
    {
        delay(500);

        Serial.print(".");

        lcd.setCursor(0, 1);
        lcd.print("Attente...     ");

        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println();
        Serial.println("WiFi connecte !");

        Serial.print("IP ESP32 : ");
        Serial.println(WiFi.localIP());

        lcd.clear();

        lcd.setCursor(0, 0);
        lcd.print("WiFi OK");

        lcd.setCursor(0, 1);
        lcd.print(WiFi.localIP());

        delay(2000);
    }
    else
    {
        Serial.println();
        Serial.println("Erreur WiFi");

        lcd.clear();

        lcd.setCursor(0, 0);
        lcd.print("Erreur WiFi");

        lcd.setCursor(0, 1);
        lcd.print("Reessayez");

        delay(3000);
    }
}

// ======================================================
// AFFICHAGE ASTRONAUTE
// ======================================================

void displayAstronautID()
{
    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("Astronaute");

    lcd.setCursor(0, 1);

    if (astronautID < 10)
    {
        lcd.print("AST-0");
    }
    else
    {
        lcd.print("AST-");
    }

    lcd.print(astronautID);
    lcd.print("  OK");
}

// ======================================================
// AFFICHAGE QUESTION
// ======================================================

void displayQuestion()
{
    lcd.clear();

    switch (currentQuestion)
    {
        // ==================================================
        // SOMMEIL
        // ==================================================

        case 0:

            lcd.setCursor(0, 0);
            lcd.print("Sommeil:");

            lcd.setCursor(0, 1);
            lcd.print(sleepHours, 1);
            lcd.print(" h");

            break;

        // ==================================================
        // STRESS
        // ==================================================

        case 1:

            lcd.setCursor(0, 0);
            lcd.print("Stress:");

            lcd.setCursor(0, 1);
            lcd.print(currentValue);
            lcd.print(" / 10");

            break;

        // ==================================================
        // FATIGUE
        // ==================================================

        case 2:

            lcd.setCursor(0, 0);
            lcd.print("Fatigue:");

            lcd.setCursor(0, 1);
            lcd.print(currentValue);
            lcd.print(" / 10");

            break;

        // ==================================================
        // MORAL
        // ==================================================

        case 3:

            lcd.setCursor(0, 0);
            lcd.print("Morale:");

            lcd.setCursor(0, 1);
            lcd.print(currentValue);
            lcd.print(" / 10");

            break;

        // ==================================================
        // ISOLEMENT
        // ==================================================

        case 4:

            lcd.setCursor(0, 0);
            lcd.print("Isolement:");

            lcd.setCursor(0, 1);
            lcd.print(currentValue);
            lcd.print(" / 10");

            break;

        // ==================================================
        // MOTIVATION
        // ==================================================

        case 5:

            lcd.setCursor(0, 0);
            lcd.print("Motivation:");

            lcd.setCursor(0, 1);
            lcd.print(currentValue);
            lcd.print(" / 10");

            break;

        // ==================================================
        // CHARGE TRAVAIL
        // ==================================================

        case 6:

            lcd.setCursor(0, 0);
            lcd.print("Charge travail:");

            lcd.setCursor(0, 1);
            lcd.print(currentValue);
            lcd.print(" / 10");

            break;
    }
}

// ======================================================
// ENVOI DES DONNEES VERS FASTAPI
// ======================================================

bool sendDataToPsychoSpace()
{
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("WiFi non connecte");
        return false;
    }

    HTTPClient http;

    Serial.println();
    Serial.println("Preparation JSON...");

    // ==================================================
    // ID ASTRONAUTE
    // ==================================================

    String astronautIDString;

    if (astronautID < 10)
    {
        astronautIDString =
            "AST-0" + String(astronautID);
    }
    else
    {
        astronautIDString =
            "AST-" + String(astronautID);
    }

    // ==================================================
    // JSON
    // ==================================================

    String json = "{";

    json += "\"astronaut_id\":\"";
    json += astronautIDString;
    json += "\",";

    json += "\"sleep_hours\":";
    json += String(sleepHours, 1);
    json += ",";

    json += "\"stress\":";
    json += String(answers[1]);
    json += ",";

    json += "\"fatigue\":";
    json += String(answers[2]);
    json += ",";

    json += "\"morale\":";
    json += String(answers[3]);
    json += ",";

    json += "\"isolation\":";
    json += String(answers[4]);
    json += ",";

    json += "\"motivation\":";
    json += String(answers[5]);
    json += ",";

    json += "\"workload\":";
    json += String(answers[6]);

    json += "}";

    // ==================================================
    // AFFICHAGE JSON
    // ==================================================

    Serial.println("JSON :");
    Serial.println(json);

    // ==================================================
    // CONNEXION SERVEUR
    // ==================================================

    http.begin(SERVER_URL);

    http.addHeader(
        "Content-Type",
        "application/json"
    );

    http.setTimeout(60000);

    // ==================================================
    // ENVOI
    // ==================================================

    Serial.println("Envoi vers PsychoSpace...");

    int httpCode = http.POST(json);

    Serial.print("Code HTTP : ");
    Serial.println(httpCode);

    // ==================================================
    // REPONSE
    // ==================================================

    if (httpCode > 0)
    {
        String response = http.getString();

        Serial.println("Reponse serveur :");
        Serial.println(response);

        http.end();

        return (
            httpCode >= 200 &&
            httpCode < 300
        );
    }

    // ==================================================
    // ERREUR
    // ==================================================

    else
    {
        Serial.print("Erreur HTTP : ");

        Serial.println(
            http.errorToString(httpCode)
        );

        http.end();

        return false;
    }
}

// ======================================================
// ENVOI DU QUESTIONNAIRE
// ======================================================

void sendQuestionnaire()
{
    state = SENDING;

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("Envoi donnees");

    lcd.setCursor(0, 1);
    lcd.print("Patientez...");

    Serial.println();
    Serial.println(
        "===== ENVOI PSYCHOSPACE ====="
    );

    bool success =
        sendDataToPsychoSpace();

    lcd.clear();

    if (success)
    {
        lcd.setCursor(0, 0);
        lcd.print("Donnees envoyees");

        lcd.setCursor(0, 1);
        lcd.print("Psychospace OK");

        Serial.println(
            "Donnees envoyees avec succes !"
        );
    }
    else
    {
        lcd.setCursor(0, 0);
        lcd.print("Erreur envoi");

        lcd.setCursor(0, 1);
        lcd.print("Serveur absent");

        Serial.println(
            "Echec de l'envoi."
        );
    }

    delay(2500);
}

// ======================================================
// CALCUL INDICE SOMMEIL
// ======================================================
//
// 8 h ou plus → 0
// 7 h         → 2
// 6 h         → 4
// 5 h         → 6
// 4 h         → 8
// 3 h ou moins→ 10
//
// Entre deux valeurs : interpolation.
// ======================================================

float calculateSleepDifficulty(float hours)
{
    if (hours >= 8.0)
    {
        return 0.0;
    }

    if (hours >= 7.0)
    {
        return 2.0 + (7.0 - hours) * 2.0;
    }

    if (hours >= 6.0)
    {
        return 4.0 + (7.0 - hours) * 2.0;
    }

    if (hours >= 5.0)
    {
        return 6.0 + (6.0 - hours) * 2.0;
    }

    if (hours >= 4.0)
    {
        return 8.0 + (5.0 - hours) * 2.0;
    }

    return 10.0;
}

// ======================================================
// CALCUL INDICE GLOBAL
// ======================================================
//
// Moral et motivation sont inverses :
//
// Moral 10 → difficulté 0
// Moral 0  → difficulté 10
//
// Motivation 10 → difficulté 0
// Motivation 0  → difficulté 10
//
// Les autres sont directs.
//
// ======================================================

float calculateGlobalIndex()
{
    float sleepIndex =
        calculateSleepDifficulty(sleepHours);

    float stressIndex =
        answers[1];

    float fatigueIndex =
        answers[2];

    float moraleIndex =
        10.0 - answers[3];

    float isolationIndex =
        answers[4];

    float motivationIndex =
        10.0 - answers[5];

    float workloadIndex =
        answers[6];

    float total =
        sleepIndex +
        stressIndex +
        fatigueIndex +
        moraleIndex +
        isolationIndex +
        motivationIndex +
        workloadIndex;

    return total / 7.0;
}

// ======================================================
// RESULTAT LOCAL
// ======================================================

void displayResult()
{
    float globalIndex =
        calculateGlobalIndex();

    // ==================================================
    // AFFICHAGE SERIAL
    // ==================================================

    Serial.println();
    Serial.println(
        "===== ANALYSE PSYCHOSPACE ====="
    );

    Serial.print(
        "Indice global : "
    );

    Serial.println(
        globalIndex,
        2
    );

    // ==================================================
    // NIVEAU
    // ==================================================

    if (globalIndex < 5.0)
    {
        lcd.clear();

        lcd.setCursor(0, 0);
        lcd.print("ETAT NORMAL");

        lcd.setCursor(0, 1);
        lcd.print("Indice ");
        lcd.print(globalIndex, 1);

        Serial.println(
            "Niveau : NORMAL"
        );

        signalOK();
    }

    else if (globalIndex < 8.0)
    {
        lcd.clear();

        lcd.setCursor(0, 0);
        lcd.print("A CONTROLER");

        lcd.setCursor(0, 1);
        lcd.print("Indice ");
        lcd.print(globalIndex, 1);

        Serial.println(
            "Niveau : A CONTROLER"
        );

        signalAttention();
    }

    else
    {
        lcd.clear();

        lcd.setCursor(0, 0);
        lcd.print("CRITIQUE");

        lcd.setCursor(0, 1);
        lcd.print("Verifier etat");

        Serial.println(
            "Niveau : CRITIQUE"
        );

        signalAttentionForte();
    }

    // ==================================================
    // INDICATEURS IMPORTANTS
    // ==================================================

    Serial.println();
    Serial.println("Indicateurs :");

    if (answers[1] >= 8)
    {
        Serial.println(
            "- Stress eleve"
        );
    }

    if (answers[2] >= 8)
    {
        Serial.println(
            "- Fatigue elevee"
        );
    }

    if (answers[3] <= 3)
    {
        Serial.println(
            "- Moral faible"
        );
    }

    if (answers[4] >= 8)
    {
        Serial.println(
            "- Isolement social eleve"
        );
    }

    if (answers[5] <= 3)
    {
        Serial.println(
            "- Motivation faible"
        );
    }

    if (answers[6] >= 8)
    {
        Serial.println(
            "- Charge de travail elevee"
        );
    }

    // ==================================================
    // PAUSE
    // ==================================================

    delay(2000);

    // ==================================================
    // ENVOI SERVEUR
    // ==================================================

    sendQuestionnaire();

    // ==================================================
    // RESET
    // ==================================================

    currentQuestion = 0;

    currentValue = 5;

    sleepHours = 7.0;

    // ==================================================
    // RETOUR ID
    // ==================================================

    state = SELECT_ID;

    displayAstronautID();
}

// ======================================================
// SETUP
// ======================================================

void setup()
{
    Serial.begin(115200);

    delay(1000);

    Serial.println();

    Serial.println(
        "================================"
    );

    Serial.println(
        "     PSYCHOSPACE - ESP32"
    );

    Serial.println(
        "================================"
    );

    // ==================================================
    // BUZZER
    // ==================================================

    setupBuzzer();

    // ==================================================
    // JOYSTICK
    // ==================================================

    pinMode(
        JOY_SW,
        INPUT_PULLUP
    );

    // ==================================================
    // I2C
    // ==================================================

    Wire.begin(
        21,
        22
    );

    // ==================================================
    // LCD
    // ==================================================

    lcd.init();

    lcd.backlight();

    // ==================================================
    // DEMARRAGE
    // ==================================================

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("PSYCHOSPACE");

    lcd.setCursor(0, 1);
    lcd.print("Initialisation");

    delay(2000);

    // ==================================================
    // WIFI
    // ==================================================

    connectWiFi();

    // ==================================================
    // PREMIER ECRAN
    // ==================================================

    displayAstronautID();

    Serial.println();
    Serial.println("Pret !");
}

// ======================================================
// LOOP
// ======================================================

void loop()
{
    // ==================================================
    // LECTURE JOYSTICK
    // ==================================================

    int y = analogRead(JOY_Y);

    // ==================================================
    // BOUTON
    // ==================================================

    bool buttonPressed =
        (digitalRead(JOY_SW) == LOW);

    // ==================================================
    // SELECTION ASTRONAUTE
    // ==================================================

    if (state == SELECT_ID)
    {
        // ------------------------------------------------
        // HAUT
        // ------------------------------------------------

        if (
            y > JOY_CENTER_Y + DEAD_ZONE &&
            millis() - lastAction > ACTION_DELAY
        )
        {
            astronautID++;

            if (astronautID > 99)
            {
                astronautID = 1;
            }

            displayAstronautID();

            lastAction = millis();
        }

        // ------------------------------------------------
        // BAS
        // ------------------------------------------------

        if (
            y < JOY_CENTER_Y - DEAD_ZONE &&
            millis() - lastAction > ACTION_DELAY
        )
        {
            astronautID--;

            if (astronautID < 1)
            {
                astronautID = 99;
            }

            displayAstronautID();

            lastAction = millis();
        }

        // ------------------------------------------------
        // VALIDATION
        // ------------------------------------------------

        if (
            buttonPressed &&
            millis() - lastAction > ACTION_DELAY
        )
        {
            currentQuestion = 0;

            currentValue = 5;

            sleepHours = 7.0;

            state = QUESTIONNAIRE;

            displayQuestion();

            lastAction = millis();

            delay(50);
        }
    }

    // ==================================================
    // QUESTIONNAIRE
    // ==================================================

    else if (state == QUESTIONNAIRE)
    {
        // ==================================================
        // SOMMEIL
        // ==================================================

        if (currentQuestion == 0)
        {
            // ------------------------------------------------
            // +0.5 H
            // ------------------------------------------------

            if (
                y > JOY_CENTER_Y + DEAD_ZONE &&
                millis() - lastAction > ACTION_DELAY
            )
            {
                sleepHours += 0.5;

                if (sleepHours > 12.0)
                {
                    sleepHours = 12.0;
                }

                displayQuestion();

                lastAction = millis();
            }

            // ------------------------------------------------
            // -0.5 H
            // ------------------------------------------------

            if (
                y < JOY_CENTER_Y - DEAD_ZONE &&
                millis() - lastAction > ACTION_DELAY
            )
            {
                sleepHours -= 0.5;

                if (sleepHours < 0.0)
                {
                    sleepHours = 0.0;
                }

                displayQuestion();

                lastAction = millis();
            }
        }

        // ==================================================
        // QUESTIONS 2 A 7
        // ==================================================

        else
        {
            // ------------------------------------------------
            // +1
            // ------------------------------------------------

            if (
                y > JOY_CENTER_Y + DEAD_ZONE &&
                millis() - lastAction > ACTION_DELAY
            )
            {
                currentValue++;

                if (currentValue > 10)
                {
                    currentValue = 10;
                }

                displayQuestion();

                lastAction = millis();
            }

            // ------------------------------------------------
            // -1
            // ------------------------------------------------

            if (
                y < JOY_CENTER_Y - DEAD_ZONE &&
                millis() - lastAction > ACTION_DELAY
            )
            {
                currentValue--;

                if (currentValue < 0)
                {
                    currentValue = 0;
                }

                displayQuestion();

                lastAction = millis();
            }
        }

        // ==================================================
        // VALIDATION QUESTION
        // ==================================================

        if (
            buttonPressed &&
            millis() - lastAction > ACTION_DELAY
        )
        {
            // ------------------------------------------------
            // SOMMEIL
            // ------------------------------------------------

            if (currentQuestion == 0)
            {
                answers[0] =
                    (int)(sleepHours * 2);

                Serial.print(
                    "Sommeil : "
                );

                Serial.print(
                    sleepHours
                );

                Serial.println(" h");
            }

            // ------------------------------------------------
            // AUTRES CRITERES
            // ------------------------------------------------

            else
            {
                answers[currentQuestion] =
                    currentValue;

                Serial.print(
                    "Question "
                );

                Serial.print(
                    currentQuestion + 1
                );

                Serial.print(
                    " : "
                );

                Serial.println(
                    currentValue
                );
            }

            // ------------------------------------------------
            // QUESTION SUIVANTE
            // ------------------------------------------------

            currentQuestion++;

            // ------------------------------------------------
            // FIN
            // ------------------------------------------------

            if (
                currentQuestion >= TOTAL_QUESTIONS
            )
            {
                state = RESULT;

                displayResult();
            }

            // ------------------------------------------------
            // CONTINUER
            // ------------------------------------------------

            else
            {
                currentValue = 5;

                displayQuestion();
            }

            lastAction = millis();

            delay(50);
        }
    }

    // ==================================================
    // PETITE PAUSE
    // ==================================================

    delay(10);
}
