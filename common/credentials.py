from os import getenv
from pathlib import Path

from hvac import Client


def _auth():
    creds_path = getenv('VAULT_CREDS')
    if creds_path is None:
        raise RuntimeError('Missing required VAULT_CREDS environment variable')
    creds = Path(creds_path).read_text().strip().split('\n', 2)
    client = Client(url=creds[0])
    client.auth.userpass.login(
        username=creds[1],
        password=creds[2],
    )
    return client


def _get_secret(client, key):
    read_response = client.secrets.kv.v2.read_secret_version(path=key)
    data = read_response['data']['data']
    if len(data) == 1 and list(data.keys())[0] == 'value':
        data = data['value']
    return data


def get_secrets(*keys):
    client = _auth()
    secrets = {}
    for key in keys:
        secrets[key] = _get_secret(client, key)
    return secrets
