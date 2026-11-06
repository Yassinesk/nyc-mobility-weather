# NYC Mobility & Weather

Pipeline ETL mensuel en Python et PostgreSQL pour étudier les liens entre la météo et l’activité des taxis jaunes à New York. Le prototype couvre janvier 2026.

## Sources et traitement

- [NYC Taxi & Limousine Commission](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) — trajets Yellow Taxi, publiés en Parquet mensuel.
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) — température, pluie, neige et vent horaires pour un point de référence à New York.

Le pipeline lit les deux sources à distance. Il filtre les courses sans date de départ, nombre de passagers, code tarifaire, supplément de congestion, frais d’aéroport ou montant total, puis conserve les montants strictement positifs. Les analyses portent donc sur les courses retenues. Les cumuls de pluie et de neige sont rattachés au début du créneau qu’ils couvrent. La clé `hour_key` associe plusieurs courses à une observation météo horaire.

## Installation

Prérequis : Python, un serveur PostgreSQL accessible et une connexion Internet pour les sources.

```bash
git clone https://github.com/Yassinesk/nyc-mobility-weather.git
cd nyc-mobility-weather
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pandas pyarrow requests "psycopg[binary]"
```

## Préparer PostgreSQL

Exécuter cette commande dans une session connectée à la base d’administration `postgres` si la base du projet doit être créée.

```sql
CREATE DATABASE nyc_mobility;
```

Ouvrir ensuite une nouvelle session SQL connectée à `nyc_mobility` et exécuter le script suivant.

```sql
CREATE TABLE IF NOT EXISTS etl_loaded_months (
    source_month DATE PRIMARY KEY,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS weather (
    hour_key TEXT PRIMARY KEY,
    time TIMESTAMP NOT NULL,
    temperature_2m DOUBLE PRECISION,
    rain DOUBLE PRECISION,
    snowfall DOUBLE PRECISION,
    wind_speed_10m DOUBLE PRECISION,
    year SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    day SMALLINT NOT NULL,
    hour_of_day SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS taxi_yellow (
    trip_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_month DATE NOT NULL,
    vendor_id INTEGER,
    tpep_pickup_datetime TIMESTAMP NOT NULL,
    tpep_dropoff_datetime TIMESTAMP,
    passenger_count INTEGER,
    trip_distance DOUBLE PRECISION,
    ratecode_id INTEGER,
    store_and_fwd_flag TEXT,
    pu_location_id INTEGER,
    do_location_id INTEGER,
    payment_type INTEGER,
    fare_amount NUMERIC,
    extra NUMERIC,
    mta_tax NUMERIC,
    tip_amount NUMERIC,
    tolls_amount NUMERIC,
    improvement_surcharge NUMERIC,
    total_amount NUMERIC,
    congestion_surcharge NUMERIC,
    airport_fee NUMERIC,
    cbd_congestion_fee NUMERIC,
    year SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    day SMALLINT NOT NULL,
    hour_of_day SMALLINT NOT NULL,
    hour_key TEXT NOT NULL REFERENCES weather (hour_key)
);
```

Créer `src/Utils/config_local.py` avec son propre mot de passe PostgreSQL. Ce fichier est ignoré par Git.

```python
POSTGRES_PASSWORD = "votre_mot_de_passe_local"
```

Les paramètres par défaut se trouvent dans `src/Utils/Configurations.py`. Ils pointent vers `localhost:5432`, avec l’utilisateur `postgres` et la base `nyc_mobility`.

## Exécuter et vérifier

```bash
python src/main.py
```

Avec une table de suivi vide, le pipeline traite janvier 2026. Après un chargement réussi, le prochain lancement traite le mois suivant. La météo est chargée avant les courses. Le mois source permet de remplacer les lignes du fichier traité, et le succès est enregistré dans la même transaction que le chargement.

```sql
SELECT source_month, loaded_at
FROM etl_loaded_months
ORDER BY source_month;

SELECT source_month, COUNT(*) AS courses_retenues
FROM taxi_yellow
GROUP BY source_month
ORDER BY source_month;
```

Le mois source identifie le fichier TLC. Pour les analyses de janvier, filtrer la date de prise en charge du 1er janvier inclus au 1er février exclu.

## Organisation du dépôt

- `src/main.py` — point d’entrée du pipeline.
- `src/Utils/` — fonctions d’extraction et de chargement, configuration PostgreSQL.
- `notebooks/EDA_projet_Mobility.ipynb` — exploration des données et validation du rapprochement horaire.

Le lancement est manuel. GitHub Actions est une piste pour planifier le traitement mensuel.
