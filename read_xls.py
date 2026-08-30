import pandas as pd
import json
try:
    df = pd.read_excel('FormatosSalida/COMPRAS.xls')
    data = {
        'columns': df.columns.tolist(),
        'head': df.head(1).to_dict(orient='records')
    }
    with open('output.json', 'w') as f:
        json.dump(data, f, indent=4)
    print("Success")
except Exception as e:
    print(f"Error: {e}")
