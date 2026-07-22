# Serveur communautaire AntiBrouteur

## Démarrage local

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

Dans l’émulateur Android, l’adresse par défaut `http://10.0.2.2:8080` pointe vers ce serveur.

Pour un téléphone réel, déployez l’API sur un serveur HTTPS et saisissez son URL dans :
**Paramètres → Serveur communautaire**.

Le serveur refuse qu’une même installation signale deux fois le même numéro.
