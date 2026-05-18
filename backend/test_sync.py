import requests
import json
from datetime import datetime

url = "http://localhost:8000/api/sync"
payload = {
    "cnpj": "12345678000100",
    "type": "VENDAS",
    "content": {
        "vendas_diarias": [
            {"data": "2026-05-01", "faturamento": 1500.50, "pedidos": 10},
            {"data": "2026-05-02", "faturamento": 2300.00, "pedidos": 15}
        ]
    },
    "timestamp": datetime.now().isoformat()
}

print(f"Enviando dados para {url}...")
try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Erro: {e}")
