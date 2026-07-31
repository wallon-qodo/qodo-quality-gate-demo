import requests

def send(url: str, body: dict):
    return requests.post(url, json=body, verify=False)
