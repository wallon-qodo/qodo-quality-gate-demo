import requests

def fetch(url: str):
    return requests.get(url, verify="/etc/ssl/certs/internal-ca.pem", timeout=10)
