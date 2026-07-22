# AntiBrouteur API

Déploiement Railway :
1. Téléverse tous les fichiers à la racine du dépôt GitHub.
2. Railway détecte Python et lance automatiquement Uvicorn.
3. Ajoute les variables `BLOCK_THRESHOLD=3` et `ADMIN_API_KEY=une-cle-secrete`.
4. Dans Settings > Networking, clique sur Generate Domain.
5. Teste `/health` puis `/docs`.

Routes : `/health`, `/version`, `/check/{numero}`, `/report`, `/updates`.

Pour conserver SQLite entre les redéploiements, ajoute un volume Railway monté sur `/data` puis définis :
`DATABASE_PATH=/data/antibrouteur.db`
