# 🤖 KomradeBot - Bot Discord Multifonctions

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Discord.py](https://img.shields.io/badge/Discord.py-2.5.2-brightgreen.svg)
![Docker](https://img.shields.io/badge/Docker-Compatible-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Un bot Discord complet développé en Python avec plus de 20 commandes pour la musique, le divertissement et les utilitaires !**

## ✨ Fonctionnalités

### 🎵 **Musique YouTube**

-   Lecture de musique depuis YouTube (URL ou recherche)
-   File d'attente avec gestion complète
-   Contrôles : pause, reprendre, skip, stop
-   Déconnexion automatique après 5 minutes d'inactivité

### 🎮 **Divertissement**

-   Mèmes aléatoires depuis Reddit
-   Photos d'animaux mignons (chats, chiens, renards)
-   Citations inspirantes
-   Mini-jeu Pierre-Feuille-Ciseaux
-   Blagues françaises (6 catégories : dev, limites, beauf, etc.)

### 🔧 **Utilitaires**

-   Prix des cryptomonnaies en temps réel (Bitcoin, Ethereum)
-   Météo pour n'importe quelle ville
-   Système de sondages personnalisés
-   Système de rappels programmés

### 📊 **Gestion Communautaire**

-   Sondages avec réactions automatiques
-   Rappels personnels et publics (admins)
-   Menu d'aide intégré
-   Informations détaillées du bot
-   Système XP/niveaux automatique
-   Statistiques d'activité complètes

## 🚀 Installation

### Prérequis

-   Docker et Docker Compose
-   Token de bot Discord
-   Clé API OpenWeather (optionnel)

### 📋 Configuration

1. **Cloner le projet :**

```bash
git clone <votre-repo>
cd DiscordBOT
```

2. **Créer le fichier `.env` :**

```bash
# OBLIGATOIRE
TOKEN=votre_token_discord_ici

# OPTIONNEL (améliore la météo)
OPENWEATHER_API_KEY=votre_clé_openweather

# OPTIONNEL (blagues françaises)
BLAGUES_API_TOKEN=votre_token_blagues_api
```

3. **Créer le répertoire de données :**

```bash
mkdir data
```

4. **Lancer avec Docker :**

```bash
docker-compose up --build
```

Le répertoire `./data` sera automatiquement monté dans le container pour persister la base de données et les caches API.

## 🔑 Obtenir les Clés API

### Discord Bot Token

1. Aller sur https://discord.com/developers/applications
2. Créer une nouvelle application
3. Aller dans "Bot" → Créer un bot
4. Copier le token dans `.env`

### OpenWeather API (Optionnel)

1. S'inscrire sur https://openweathermap.org/api
2. Récupérer la clé gratuite
3. L'ajouter dans `.env`

**Note :** Sans clé OpenWeather, la météo utilisera un service de fallback.

### Blagues API (Optionnel)

1. Aller sur https://www.blagues-api.fr/
2. Créer un compte gratuit
3. Récupérer le token Bearer dans votre profil
4. L'ajouter dans `.env`

**Note :** Sans token Blagues API, les commandes `/blague` afficheront un message d'aide.

## 🎯 Système XP/Niveaux

Le bot inclut un système de niveaux automatique :

### 📊 **Fonctionnement**

-   **+15 à 50 XP** par message (basé sur la longueur)
-   **Cooldown de 60 secondes** entre chaque gain d'XP
-   **Niveaux progressifs** : 100 XP pour le niveau 2, puis +50 XP par niveau
-   **Notifications automatiques** lors des montées de niveau

### 📈 **Statistiques trackées**

-   Messages envoyés par utilisateur et serveur
-   Heures d'activité les plus fréquentes
-   Jours de la semaine les plus actifs
-   Classement des utilisateurs les plus actifs

### 🗄️ **Base de données**

-   **SQLite** intégrée dans le container Docker
-   **Persistance** des données entre redémarrages
-   **Performances optimisées** pour les requêtes stats

## 📖 Commandes Disponibles

### 🎵 **Musique** (7 commandes)

| Commande                | Description                        |
| ----------------------- | ---------------------------------- |
| `/play [url/recherche]` | Joue de la musique YouTube         |
| `/pause`                | Met en pause la musique            |
| `/resume`               | Reprend la musique                 |
| `/skip`                 | Passe à la chanson suivante        |
| `/stop`                 | Arrête la musique (déco auto 5min) |
| `/leave`                | Déconnecte le bot immédiatement    |
| `/queue`                | Affiche la file d'attente          |

### 🎮 **Divertissement** (8 commandes)

| Commande              | Description                            |
| --------------------- | -------------------------------------- |
| `/meme`               | Mème aléatoire depuis Reddit           |
| `/chaton`             | Photo de chat mignon                   |
| `/chien`              | Photo de chien mignon                  |
| `/fox`                | Photo de renard mignon                 |
| `/quote`              | Citation inspirante                    |
| `/pfc [choix]`        | Pierre-Feuille-Ciseaux                 |
| `/blague [catégorie]` | Blague française (6 types disponibles) |
| `/blagueinfo`         | Statistiques de l'API Blagues          |

### 🔧 **Utilitaires** (5 commandes)

| Commande                     | Description                          |
| ---------------------------- | ------------------------------------ |
| `/btc`                       | Prix du Bitcoin en temps réel        |
| `/eth`                       | Prix d'Ethereum en temps réel        |
| `/weather [ville]`           | Météo d'une ville                    |
| `/poll [question] [options]` | Sondage personnalisé (max 5 options) |
| `/quickpoll [question]`      | Sondage Oui/Non rapide               |

### ⏰ **Rappels** (2 commandes)

| Commande                      | Description                      |
| ----------------------------- | -------------------------------- |
| `/remindme [durée] [message]` | Rappel personnel                 |
| `/remind [durée] [message]`   | Rappel public (admin uniquement) |

**Formats de durée :** `5m`, `2h`, `1d` (maximum 7 jours)

### 📊 **Stats & XP** (3 commandes)

| Commande               | Description                    |
| ---------------------- | ------------------------------ |
| `/level [utilisateur]` | Affiche niveau et XP d'un user |
| `/leaderboard`         | Classement des niveaux top 10  |
| `/stats`               | Statistiques complètes serveur |

**Système XP :** +15-50 XP par message (cooldown 60s), montée de niveau automatique

### ℹ️ **Aide** (2 commandes)

| Commande | Description                    |
| -------- | ------------------------------ |
| `/help`  | Menu d'aide complet et stylé   |
| `/info`  | Informations techniques du bot |

## 🛠️ Technologies Utilisées

-   **Python 3.11+** - Langage principal
-   **Discord.py 2.5.2** - Librairie Discord
-   **yt-dlp** - Téléchargement YouTube
-   **FFmpeg** - Processing audio
-   **aiohttp** - Requêtes HTTP asynchrones
-   **SQLite** - Base de données stats/XP
-   **Docker** - Conteneurisation

## 🌐 APIs Externes

-   **YouTube** - Extraction audio (yt-dlp)
-   **CoinGecko** - Prix des cryptomonnaies (gratuit)
-   **OpenWeatherMap** - Données météo (optionnel)
-   **Reddit API** - Mèmes aléatoires
-   **TheCatAPI / TheDogAPI** - Photos d'animaux
-   **ZenQuotes** - Citations inspirantes
-   **Blagues-API** - Blagues françaises (2700+ blagues, optionnel)

## 🔧 Configuration Docker

Le bot utilise `docker-compose.yml` avec :

-   **Image :** `komradebot:2.0` (taguée)
-   **Mode réseau :** `host` (pour la voix Discord)
-   **Volumes :**
    -   `.env` monté pour les variables
    -   `./data` monté pour la persistance (DB SQLite + cache API)
-   **Redémarrage :** Automatique sauf arrêt manuel

### 📁 **Structure des données persistantes**

```
./data/
├── bot_data.db          # Base SQLite (XP, stats, utilisateurs)
└── openweather_usage.json  # Cache limite API météo
```

Ces fichiers sont **automatiquement créés** au premier lancement et **persistent** entre les redémarrages.

## 🚨 Dépannage

### Problèmes de connexion vocale

-   **WebSocket 4006 :** Bug Discord connu, le bot retry automatiquement
-   **FFmpeg manquant :** Installé automatiquement dans le container

### Variables d'environnement

-   Vérifier que `TOKEN` existe dans `.env`
-   Redémarrer après modification : `docker-compose restart`

### Commandes slash non visibles

```bash
# Forcer la synchronisation avec rebuild complet
docker-compose down
docker-compose up --build

# Le rebuild créera l'image komradebot:2.0
```

## 📈 Statistiques

-   **27+ commandes** disponibles
-   **7 catégories** de fonctionnalités
-   **Auto-déconnexion** intelligente
-   **APIs multiples** intégrées
-   **Interface française** complète
-   **Base SQLite** intégrée

## 📝 Logs & Monitoring

Les logs sont visibles avec :

```bash
docker logs discordbot-komradebot-1 --follow
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature
3. Commit les changements
4. Push et créer une Pull Request

## 📄 License

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

**Développé avec ❤️ en Python | KomradeBot v2.0**
