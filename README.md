# AntiBrouteur API — correction des numéros

Cette version accepte les formats suivants :

- `0612345678`
- `06 12 34 56 78`
- `+33612345678`
- `+33 6 12 34 56 78`
- `0033612345678`
- les numéros internationaux E.164, par exemple `+12025550100`

Les numéros français sont enregistrés sous la forme `+33...`.

## Fichiers à mettre sur GitHub

Remplace les anciens fichiers du dépôt par :

- `main.py`
- `requirements.txt`
- `render.yaml`

Puis fais un commit. Render doit redéployer automatiquement.

## Variables Render

La variable `DATABASE_URL` doit être reliée à la base `antibrouteur-db`.

La variable `REPORT_THRESHOLD` vaut `3` par défaut. Un numéro apparaît dans
`GET /v1/community/numbers` après trois signalements venant de trois
`installation_id` différents.

## Test Swagger

Ouvre `/docs`, puis exécute trois fois `POST /v1/community/report` avec le même
numéro et trois identifiants différents :

```json
{
  "number": "0612345678",
  "category": "arnaque",
  "installation_id": "test-antibrouteur-001"
}
```

Puis change l'identifiant en `test-antibrouteur-002` et
`test-antibrouteur-003`.

La réponse POST indique désormais :

- `inserted`
- `reports`
- `required`
- `published`

Ensuite, ouvre `GET /v1/community/numbers`.
