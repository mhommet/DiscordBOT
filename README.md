## Installation

```
docker compose up -d --build
```

## Fonctionnalités

-> Musique (Lecture depuis YouTube)

-> Plus de commandes utilitaires et d'administration à venir...

### Liste des commandes disponibles :

**Musique**

```
$play <url>/<nom de la chanson> : Joue de la musique depuis YouTube
$play_song <numéro de la chanson dans la file d'attente>
$queue : Affiche la file d'attente
$pause : Met en pause la musique
$resume : Reprend la lecture de la musique
$skip : Passe à la chanson suivante
$leave : Quitte le canal vocal
$clear : Arrête la musique et vide la file d'attente
```

**Utilitaires**

```
$help : Affiche la liste des commandes
```

## Informations supplémentaires

- Le bot fournit des commandes musicales.
- Pour utiliser le bot, vous devez définir votre token Discord dans un fichier `.env` à la racine du projet.
