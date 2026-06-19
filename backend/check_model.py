import pandas as pd
from pathlib import Path

data_dir = Path(r'f:\FYP\archive\cleaned_dataset')
charging_df    = pd.read_csv(data_dir / 'charging_100_cycles_with_soc.csv')
discharging_df = pd.read_csv(data_dir / 'discharging_100_cycles_with_soc.csv')

combined = pd.concat([charging_df, discharging_df])
print('Training data ranges:')
print('  Voltage:', combined['Voltage_measured'].min(), 'to', combined['Voltage_measured'].max(), 'V')
print('  Current:', combined['Current_measured'].min(), 'to', combined['Current_measured'].max(), 'A')
print('  Temp   :', combined['Temperature_measured'].min(), 'to', combined['Temperature_measured'].max(), 'C')
print('  SoC    :', combined['SoC'].min(), 'to', combined['SoC'].max())
print()

# What does model predict for different current values at our actual voltage?
import joblib
import numpy as np

model = joblib.load(r'f:\FYP\archive\cleaned_dataset\data\backend\models\lightgbm_soc_model.pkl')

print('SoC predictions at V=3.52V (our hardware cell voltage):')
for current in [-2.0, -1.0, -0.5, 0.06, 0.5, 1.0, 2.0]:
    is_ch = 1 if current > 0 else 0
    p = current * 3.52
    row = pd.DataFrame([{
        'Voltage_measured': 3.52,
        'Current_measured': current,
        'Temperature_measured': 30.3,
        'Is_Charging': is_ch,
        'Voltage_Current_Product': p,
        'Power': p
    }])
    pred = float(np.clip(model.predict(row)[0], 0, 100))
    print(f'  I={current:5.2f}A -> SoC={pred:.1f}%')
