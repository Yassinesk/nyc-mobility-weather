from datetime import date

import pandas as pd

from Utils.Configurations import ConfigurationParams
from Utils.utils_functions import (
    creer_cle_horaire,
    load_data,
    prochain_mois,
    read_taxi_data,
    read_weather_data,
)


def ajouter_cle_horaire(df, colonne_date):
    horodatage = pd.to_datetime(df[colonne_date])

    df["year"] = horodatage.dt.year
    df["month"] = horodatage.dt.month
    df["day"] = horodatage.dt.day
    df["hour_of_day"] = horodatage.dt.hour
    df["hour_key"] = creer_cle_horaire(df)


def main():
    with ConfigurationParams.connect() as connexion:
        dernier_mois = connexion.execute(
            "SELECT MAX(source_month) FROM etl_loaded_months"
        ).fetchone()[0]

    periode_precedente = (
        (dernier_mois.year, dernier_mois.month)
        if dernier_mois is not None
        else None
    )
    annee, mois = prochain_mois(periode_precedente)
    mois_source = date(annee, mois, 1)

    print(f"Période à traiter : {annee}-{mois:02d}")

    df_taxi = read_taxi_data(annee, mois)
    df_weather = read_weather_data(annee, mois)

    # Apply the filtering rules defined during the exploratory analysis.
    colonnes_requises = [
        "tpep_pickup_datetime",
        "passenger_count",
        "RatecodeID",
        "congestion_surcharge",
        "Airport_fee",
        "total_amount",
    ]

    taxi = df_taxi.dropna(subset=colonnes_requises)
    taxi = taxi.loc[taxi["total_amount"].gt(0)].copy()

    if taxi.empty:
        raise ValueError(f"Aucune course retenue pour {mois_source:%Y-%m}.")

    taxi = taxi.rename(columns={
        "VendorID": "vendor_id",
        "RatecodeID": "ratecode_id",
        "PULocationID": "pu_location_id",
        "DOLocationID": "do_location_id",
        "Airport_fee": "airport_fee",
    })
    taxi[["passenger_count", "ratecode_id"]] = (
        taxi[["passenger_count", "ratecode_id"]].astype("Int64")
    )

    # Some TLC files omit this nullable column.
    if "store_and_fwd_flag" not in taxi.columns:
        taxi["store_and_fwd_flag"] = None

    ajouter_cle_horaire(taxi, "tpep_pickup_datetime")
    taxi["source_month"] = mois_source

    # Open-Meteo labels rain and snowfall at the end of their hourly window.
    meteo = df_weather.copy()
    meteo["time"] = pd.to_datetime(meteo["time"])

    if meteo["time"].isna().any() or not meteo["time"].is_unique:
        raise ValueError("Les horodatages météo doivent être renseignés et uniques.")

    cumuls = meteo.set_index("time")[["rain", "snowfall"]]
    fin_creneau = meteo["time"] + pd.Timedelta(hours=1)
    meteo["rain"] = fin_creneau.map(cumuls["rain"])
    meteo["snowfall"] = fin_creneau.map(cumuls["snowfall"])

    # Keep only hours for which the API returned the end of the window.
    meteo = meteo.loc[fin_creneau.isin(cumuls.index)].copy()
    ajouter_cle_horaire(meteo, "time")

    heures_manquantes = taxi.loc[
        ~taxi["hour_key"].isin(meteo["hour_key"]), "hour_key"
    ].unique()
    if len(heures_manquantes):
        raise ValueError(f"Créneaux météo manquants : {heures_manquantes[:5].tolist()}")

    # Load both tables and record success in one transaction.
    with ConfigurationParams.connect() as connexion:
        nb_meteo = load_data(connexion, meteo, "weather")

        connexion.execute(
            "DELETE FROM taxi_yellow WHERE source_month = %s",
            (mois_source,),
        )
        nb_taxis = load_data(connexion, taxi, "taxi_yellow")

        connexion.execute(
            """
            INSERT INTO etl_loaded_months (source_month)
            VALUES (%s)
            ON CONFLICT (source_month) DO NOTHING
            """,
            (mois_source,),
        )

    print(f"Courses retenues : {nb_taxis:,} sur {len(df_taxi):,}")
    print(f"Chargement réussi : {nb_meteo:,} lignes météo et {nb_taxis:,} courses.")

if __name__ == "__main__":
    main()