import pandas as pd

df = pd.read_csv('mortality_260115_READY_FOR_UPLOAD.csv', encoding='latin-1')
print(f'Total rows: {len(df)}')
print(f'\nColumns:')
for col in df.columns:
    print(f'  - {col}')
print(f'\nFirst row:')
for col in df.columns:
    print(f'{col}: {df.iloc[0][col]}')
