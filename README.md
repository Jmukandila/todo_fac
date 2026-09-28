# 🎓 Todo Fac - Gestionnaire Collaboratif de Devoirs

Application web collaborative en Python Flask permettant aux étudiants de créer des devoirs de groupe, d'inviter leurs camarades par email (via l'API Posta) et de suivre l'avancement des équipes.

## 🛠️ Stack Technique

- **Backend** : Python 3, Flask, Flask-SQLAlchemy (base SQLite)
- **Authentification & Sécurité** : Flask-Login, hachage de mot de passe avec Werkzeug (`generate_password_hash` / `check_password_hash`)
- **Service d'Emails** : Intégration API Posta avec simulation / mock automatique en développement
- **Frontend** : Templates Jinja2 stylisés avec Tailwind CSS

---

## 📂 Structure du Projet

```text
todo_fac/
├── app.py                  # Application Flask principale (modèles, routes, logique métier)
├── services/
│   ├── __init__.py
│   └── posta.py            # Service d'envoi d'e-mails via l'API Posta
├── templates/
│   ├── index.html          # Tableau de bord principal (création de projet, liste, invitations)
│   ├── login.html          # Page de connexion
│   └── register.html       # Page d'inscription
├── instance/
│   └── todo_fac.db         # Base de données SQLite
└── venv/                   # Environnement virtuel Python
```

---

## 🚀 Lancement de l'Application

1. **Activer l'environnement virtuel :**
   ```bash
   source venv/bin/activate
   ```

2. **(Optionnel) Configurer les variables d'environnement Posta :**
   ```bash
   export POSTA_API_KEY="votre_cle_api_posta"
   export POSTA_API_URL="https://api.posta.tech/v1/send" # ou l'URL de votre instance
   ```
   *Note : En l'absence de clé API, le service fonctionne en mode simulation (logs console).*

3. **Lancer le serveur de développement :**
   ```bash
   python3 app.py
   ```
   L'application est accessible à l'adresse : `http://127.0.0.1:5000`

---

## ✨ Fonctionnalités Implémentées

1. **Inscription et Connexion sécurisées** :
   - Hachage robuste des mots de passe.
   - Gestion de session utilisateur via `Flask-Login`.
   - Si un camarade a déjà été invité par son adresse e-mail avant d'avoir un compte, son inscription active automatiquement son compte et rattache ses invitations.
2. **Création de Devoir / Projet** :
   - L'utilisateur connecté devient automatiquement l'administrateur du projet.
   - Saisie du titre, de la description et des e-mails des membres invités (séparés par des virgules).
3. **Invitations par Email (Posta)** :
   - Détection des utilisateurs existants ou pré-création de comptes temporaires.
   - Création d'une invitation avec le statut `en_attente`.
   - Appel au service d'email Posta.
4. **Tableau de Bord Étudiant** :
   - Bannière d'alerte pour les invitations reçues en attente avec boutons **Accepter** et **Refuser**.
   - Liste des devoirs administrés avec visualisation en temps réel du statut de chaque membre (`Accepté ✅`, `En attente ⏳`).
   - Liste des devoirs partagés rejoints.
