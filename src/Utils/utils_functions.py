import pandas as pd
import requests
from psycopg import sql
#==========Useful functions ===================================================

#read taxi data
def read_taxi_data(annee, mois):
    nom = f"yellow_tripdata_{annee}-{mois:02d}.parquet"
    url_taxi = f"https://d37ci6vzurychx.cloudfront.net/trip-data/{nom}"
    df_taxi = pd.read_parquet(url_taxi, engine="pyarrow")
    return df_taxi

#read Weather data
def read_weather_data(annee, mois):
    debut_mois = pd.Timestamp(year=annee, month=mois, day=1)
    params = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "start_date": (debut_mois - pd.Timedelta(days=1)).date().isoformat(),
        "end_date": (debut_mois + pd.offsets.MonthBegin(1)).date().isoformat(),
        "hourly": "temperature_2m,rain,snowfall,wind_speed_10m",
        "timezone": "America/New_York",
    }
    url_meteo = "https://archive-api.open-meteo.com/v1/archive"

    response = requests.get(url_meteo, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    df_weather = pd.DataFrame(data["hourly"])
    df_weather["time"] = pd.to_datetime(df_weather["time"])
    return df_weather
def creer_cle_horaire(df):
    return (
        df["year"].astype("Int64").astype("string").str.zfill(4)
        + "-" + df["month"].astype("Int64").astype("string").str.zfill(2)
        + "-" + df["day"].astype("Int64").astype("string").str.zfill(2)
        + "-" + df["hour_of_day"].astype("Int64").astype("string").str.zfill(2)
    )




def load_data(connexion, df, table):
    if table not in {"weather", "taxi_yellow"}:
        raise ValueError(f"Table non prise en charge : {table}")

    colonnes = list(df.columns)
    noms_sql = sql.SQL(", ").join(map(sql.Identifier, colonnes))

    # Convertit NaN, NaT et pd.NA en NULL pour PostgreSQL.
    def lignes():
        for ligne in df.itertuples(index=False, name=None):
            yield tuple(None if pd.isna(valeur) else valeur for valeur in ligne)

    with connexion.cursor() as curseur:
        if table == "weather":
            mises_a_jour = sql.SQL(", ").join(
                sql.SQL("{col} = EXCLUDED.{col}").format(
                    col=sql.Identifier(colonne)
                )
                for colonne in colonnes
                if colonne != "hour_key"
            )

            requete = sql.SQL("""
                INSERT INTO weather ({colonnes})
                VALUES ({parametres})
                ON CONFLICT (hour_key) DO UPDATE SET {mises_a_jour}
            """).format(
                colonnes=noms_sql,
                parametres=sql.SQL(", ").join(
                    sql.Placeholder() for _ in colonnes
                ),
                mises_a_jour=mises_a_jour,
            )

            curseur.executemany(requete, lignes())
        else:
            requete = sql.SQL("COPY taxi_yellow ({}) FROM STDIN").format(
                noms_sql
            )

            with curseur.copy(requete) as chargement:
                for ligne in lignes():
                    chargement.write_row(ligne)

    return len(df)





def prochain_mois(dernier_mois_charge=None):
    if dernier_mois_charge is None:
        return 2026, 1

    annee, mois = dernier_mois_charge
    debut_mois = pd.Timestamp(year=annee, month=mois, day=1)
    mois_suivant = debut_mois + pd.offsets.MonthBegin(1)

    return mois_suivant.year, mois_suivant.month