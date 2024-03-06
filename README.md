# KomradeBOT (FR)

![komradebot](https://github.com/Milan144/KomradeBOT/assets/75842903/8afbfd18-83e7-4522-b528-19e75d980eca)

# Features in the future (EN)

-> Ability to define language in the .env file
-> Better TTS voice

## Installation et lancement

Définir les variables d'environnement dans un fichier .env -> comme l'exemple dans le .env.example

```docker compose up -d --build```

## Fonctionnalités

-> Musique (Lecture depuis youtube)

-> Commandes funs

-> D'autres commandes utilitaires, d'administration et fun a venir...

#### Liste des commandes disponibles:

**Musique**
```
$play <url>/<nom de la musique>: Joue de la musique depuis Youtube
$play_song <numero de la musique dans la file d'attente>
$queue: Montre la file d'attente
$pause: Met en pause la musique
$resume: Remet en route la musique
$skip: Passe à la musique suivante
$leave: Quitte le channel vocal
$clear: Stop la musique et vide la file d'attente
```
**Fun**
```
$chat <question ou message>: Pose une question à KomradeBOT (OpenAI API) and get the answer by TTS in voice channel (Il faut avoir mis un token OpenAI API dans le .env)
$magic: Fais disparaitre quelqun du channel vocal (1h de cooldown)
$k2a: Envoie une citation de Kaaris
$ano <message>: Envoie un message anonyme
$roulette: Roulette russe (5s de cooldown)
$insult <user>: Insulte un membre du serveur
```
**Utilitaires**
```
$help: Affiche la liste des commandes
```
