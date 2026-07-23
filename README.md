# AntiBrouteur API — ajout de la suppression

Cette version ajoute deux routes dans Swagger :

## 1. Supprimer complètement un numéro

`DELETE /v1/community/number/{number}`

Cette route supprime tous les signalements liés au numéro. Elle est protégée
par la variable Render `ADMIN_API_KEY`.

Dans Swagger :

1. Ouvrez la route DELETE.
2. Cliquez sur **Try it out**.
3. Dans `number`, mettez par exemple `0612345678`.
4. Dans `X-Admin-Key`, mettez la valeur de `ADMIN_API_KEY`.
5. Cliquez sur **Execute**.

## 2. Retirer un seul signalement

`DELETE /v1/community/report/{number}/{installation_id}`

Cette route retire seulement le signalement correspondant à
l'`installation_id` indiqué.

## Installation sur GitHub

Remplacez les anciens fichiers du dépôt par :

- `main.py`
- `requirements.txt`
- `render.yaml`
- `README.md`

Puis faites **Commit changes**. Render redéploiera automatiquement.

## Vérification sur Render

Dans **Environment**, vérifiez que les variables suivantes existent :

- `PYTHON_VERSION`
- `REPORT_THRESHOLD`
- `DATABASE_URL`
- `ADMIN_API_KEY`

Si `ADMIN_API_KEY` n'a pas été créée automatiquement, ajoutez-la avec :

**Add variable → Generated secret**

Nom : `ADMIN_API_KEY`

Gardez cette clé privée. Ne la placez jamais dans une capture publique,
dans GitHub ou directement dans l'application Android.
