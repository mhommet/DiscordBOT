- [FR](https://github.com/Milan144/KomradeBOT?tab=readme-ov-file#french)

- [EN](https://github.com/Milan144/KomradeBOT?tab=readme-ov-file#english)

# French

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
$ano <message>: Envoie un message anonyme
$roulette: Roulette russe (5s de cooldown)
```
**Utilitaires**
```
$help: Affiche la liste des commandes
```

## Informations supplémentaires

* Le bot utilise l'API OpenAI pour la commande `$chat`, vous devez donc disposer d'un jeton d'API pour l'utiliser.

# English

## Installation and Launching

Set environment variables in a .env file -> like the example in .env.example

`docker compose up -d --build`

## Features

-> Music (Playing from YouTube)

-> Fun commands

-> More utility, administration and fun commands to come...

### List of available commands:

**Music**
```
$play <url>/<song name>: Plays music from YouTube
$play_song <number of the song in the queue>
$queue: Shows the queue
$pause: Pauses the music
$resume: Resumes the music
$skip: Skips to the next song
$leave: Leaves the voice channel
$clear: Stops the music and clears the queue
```
**Fun**
```
$chat <question or message>: Asks KomradeBOT a question (OpenAI API) and get the answer by TTS in voice channel (You need to have set an OpenAI API token in the .env)
$magic: Makes someone disappear from the voice channel (1h cooldown)
$ano <message>: Sends an anonymous message
$roulette: Russian roulette (5s cooldown)
```
**Utilities**
```
$help: Displays the list of commands
```

## Additional Information

* The bot uses the OpenAI API for the $chat command, so you need to have an API token to use it.
