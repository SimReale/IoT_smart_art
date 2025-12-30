import time
import yaml
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from influxdb_client_3 import InfluxDBClient3
from prophet import Prophet
from prophet.serialize import model_to_json, model_from_json
from sklearn.metrics import mean_squared_error, mean_absolute_error
import schedule


# Load InfluxDB config
WORKING_DIR = Path.cwd()
CONFIG_PATH = WORKING_DIR.joinpath("influx_config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
  INFLUX_CONFIG = yaml.safe_load(_f) or {}

IDB_HOST=INFLUX_CONFIG.get("IDB_HOST", "")
IDB_TOKEN=INFLUX_CONFIG.get("IDB_TOKEN", "") 
IDB_ORG=INFLUX_CONFIG.get("IDB_ORG", "")
IDB_BUCKET=INFLUX_CONFIG.get("IDB_BUCKET", "")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def get_data_from_influx_sql(col_name, lookback_days=7):

    client = InfluxDBClient3(
        host=IDB_HOST,
        token=IDB_TOKEN,
        org=IDB_ORG,
        database=IDB_BUCKET
    )

    query = f"""
    SELECT
    MEAN({col_name}) AS "y"
    FROM "sensors"
    WHERE time >= now() - {lookback_days}d
    GROUP BY time(5m)
    """

    lower_bound = 0
    if col_name == 'temperature':
        upper_bound = np.log1p(80)
    elif col_name =='humidity':
        upper_bound = np.log1p(100)
    elif col_name == 'light':
        upper_bound = np.log1p(660)
    
    try:
        df = client.query(query=query, language="influxql").to_pandas().sort_values(by="time")
        if not df.empty:
            df['ds'] = df['time']
            df = df[['ds', 'y']].dropna().reset_index(drop=True)
            df['ds'] = pd.to_datetime(df['ds'])  # 'ds' (time) column should not contain the timezone for Prophet
            if df['ds'].dt.tz is not None:
                df['ds'] = df['ds'].dt.tz_localize(None)
            df['y'] = np.log1p(df['y'])
        else:
            df = pd.read_csv(WORKING_DIR.joinpath('data', 'default_dataset.csv')).drop(columns=['Unnamed: 0']).sort_values(by="time")
            df['ds'] = pd.to_datetime(df['time'])
            if df['ds'].dt.tz is not None:
                df['ds'] = df['ds'].dt.tz_localize(None)
            df = df[['ds', col_name]].rename(columns={col_name: 'y'})
            df = df.resample('5min', on='ds')['y'].mean().dropna().reset_index()
            df['y'] = np.log1p(df['y'])
        df['floor'] = lower_bound
        df['cap'] = upper_bound
        return df

    except Exception as e:
        logging.error(f"Query Error for {col_name}: {e}")
        return None
    finally:
        client.close()


def train_validate_and_save(field_name, lookback_days=7, mode_train='additive'):

    MODELS_DIR = WORKING_DIR.joinpath("forecasting_models")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    df = get_data_from_influx_sql(field_name, lookback_days=lookback_days)
    args = {
        'growth': 'logistic',
        'daily_seasonality': False,
        'weekly_seasonality': False, 
        'yearly_seasonality': False,
        'changepoint_prior_scale': 0.001
    }
    fourier_order_val = 20
    init_params = {}

    if MODELS_DIR.joinpath(f'model_{field_name}_default.json').exists():
        with open(MODELS_DIR.joinpath(f'model_{field_name}_default.json'), 'r') as fin:
            default_model = model_from_json(json.load(fin))

        for pname in ['k', 'm', 'sigma_obs']:
            if pname in default_model.params:
                init_params[pname] = default_model.params[pname][0][0]    
        for pname in ['delta', 'beta']:
            if pname in default_model.params:
                init_params[pname] = default_model.params[pname][0]

    # Evaluation: split with approx. 6 days for training, 1 day for validation
    train_split = 0.8571
    split_idx = int(len(df) * train_split)
    train_df = df.iloc[:split_idx]
    val_df = df.iloc[split_idx:]

    model_val = Prophet(**args)
    model_val.add_seasonality(name='daily', period=1, fourier_order=fourier_order_val, mode=mode_train)
    model_val.fit(train_df, init=init_params)
    
    forecast_val = model_val.predict(val_df[['ds', 'floor', 'cap']])
    
    y_true = np.expm1(val_df['y']).values
    y_pred = np.expm1(forecast_val['yhat']).values
    
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    
    logging.info(f"[{field_name}] RMSE: {rmse:.4f} | MAE: {mae:.4f}")
    
    # Retrain for inference
    model_final = Prophet(**args)
    model_final.add_seasonality(name='daily', period=1, fourier_order=fourier_order_val, mode=mode_train)
    model_final.fit(df, init=init_params)
    
    # Safe Write
    temp_filename = MODELS_DIR.joinpath(f"model_{field_name}.json.tmp")
    model_filename = MODELS_DIR.joinpath(f"model_{field_name}.json")
    with open(temp_filename, 'w') as fout:
        json.dump(model_to_json(model_final), fout)
    
    temp_filename.replace(model_filename)
    logging.info(f"Model saved: {model_filename}")


def job():
    logging.info("Forecasting Model job started.")
    for field, mode in zip(['temperature', 'humidity', 'light'], ['additive', 'additive', 'multiplicative']):
        train_validate_and_save(field, mode_train=mode)


if __name__ == "__main__":
    job()
    schedule.every(6).hours.do(job)
    while True:
        schedule.run_pending()
        time.sleep(60)
