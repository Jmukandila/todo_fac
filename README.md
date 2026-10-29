#  Todo Fac - Gestionnaire Collaboratif de Devoirs

Application web collaborative en Python Flask permettant aux étudiants de créer des devoirs de groupe, d'inviter leurs camarades par email (via l'API Posta) et de suivre l'avancement des équipes.

## Stack Technique

- **Backend** : Python 3, Flask, Flask-SQLAlchemy (base SQLite)
- **Authentification & Sécurité** : Flask-Login, hachage de mot de passe avec Werkzeug (`generate_password_hash` / `check_password_hash`)
- **Service d'Emails** : Intégration API Posta avec simulation / mock automatique en développement
- **Frontend** : Templates Jinja2 stylisés avec Tailwind CSS

---

##  Structure du Projet

```text
todo_fac/
├── app.py                  # Application Flask principale (modèles, routes, logique métier)
├── services/
│   ├── __init__.py
│   └── posta.py            # Service d'envoi d'e-mails via l'API Posta
├── templates/
│   ├── base.html           # Template de base (navbar, responsive, notifications)
│   ├── index.html          # Tableau de bord général (KPIs, aperçus rapides)
│   ├── creer_devoir.html   # Page dédiée : Création de devoir & invitations
│   ├── mes_devoirs.html    # Page dédiée : Mes devoirs administrés & gestion des équipes
│   ├── devoirs_partages.html # Page dédiée : Devoirs partagés avec moi & invitations en attente
│   ├── collaborateurs.html # Page dédiée : Annuaire et gestion des collaborateurs
│   ├── login.html          # Page de connexion
│   └── register.html       # Page d'inscription
├── instance/
│   └── todo_fac.db         # Base de données SQLite
└── venv/                   # Environnement virtuel Python
```

---

##  Lancement de l'Application

1. **Activer l'environnement virtuel :**
   ```bash
   source venv/bin/activate
   ```

2. **(Optionnel) Configurer les variables d'environnement Posta :**
   Créer un fichier `.env` à la racine (ou copier `.env.example`) :
   ```bash
   cp .env.example .env
   ```
   Renseigner votre clé et l'URL Posta :
   ```env
   POSTA_API_KEY="psk_votre_cle_api"
   POSTA_API_URL="https://api.goposta.dev/api/v1/emails/send" # ou l'URL de votre instance Posta
   POSTA_FROM_EMAIL=""
   ```
   *Note : En l'absence de clé API, le service fonctionne automatiquement en mode simulation (logs console).*

3. **Lancer le serveur de développement :**
   ```bash
   python3 app.py
   ```
   L'application est accessible à l'adresse : `http://127.0.0.1:5000`

---

##  Pages et Fonctionnalités

1. **Tableau de Bord Général (`/`)** :
   - Vue d'ensemble avec métriques clés (Devoirs administrés, Devoirs partagés, Collaborateurs, Invitations).
   - Accès rapide aux devoirs récents et alertes d'invitations.
2. **Créer un Devoir (`/creer-devoir`)** :
   - Formulaire dédié pour définir le titre, la description et inviter les camarades par e-mail.
   - Envoi automatique des invitations par email via Posta.
3. **Mes Devoirs (`/mes-devoirs`)** :
   - Liste des devoirs dont vous êtes l'administrateur.
   - Recherche en direct, ajout rapide de collaborateurs, relance d'invitations en attente et suppression.
4. **Devoirs Partagés (`/devoirs-partages`)** :
   - Suivi des devoirs créés par vos camarades.
   - Gestion des invitations en attente (Accepter / Décliner) et option de quitter un devoir.
5. **Liste des Collaborateurs (`/collaborateurs`)** :
   - Annuaire complet de vos camarades de promotion avec qui vous travaillez.
   - Recherche instantanée, statut de collaboration, contact par e-mail et invitation directe à un devoir.
6. **Authentification & Sécurité (`/login`, `/register`, `/logout`)** :
   - Hachage de mot de passe Werkzeug et gestion des sessions avec Flask-Login.
   - Activation automatique des comptes invités lors de leur première inscription.
