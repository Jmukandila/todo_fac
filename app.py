import os
from datetime import datetime, timezone
from flask import Flask, flash, redirect, render_template, request, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from services.posta import send_invitation_email

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "fac_secret_key_development_2026")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///todo_fac.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- CONFIGURATION FLASK-LOGIN ---
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- MODÈLES DE DONNÉES ---
class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    date_creation = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    projets_administres = db.relationship(
        "Projet", backref="admin", lazy=True, cascade="all, delete-orphan"
    )
    participations = db.relationship(
        "Invitation", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.nom} ({self.email})>"


class Projet(db.Model):
    __tablename__ = "projet"

    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date_creation = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    invitations = db.relationship(
        "Invitation", backref="projet", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Projet {self.titre}>"


class Invitation(db.Model):
    __tablename__ = "invitation"

    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    statut = db.Column(db.String(20), default="en_attente")  # 'en_attente', 'accepte', 'refuse'
    date_invitation = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Invitation Projet:{self.projet_id} User:{self.user_id} ({self.statut})>"


with app.app_context():
    db.create_all()


# --- ROUTES D'AUTHENTIFICATION ---

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not nom or not email or not password:
            flash("Tous les champs obligatoires doivent être renseignés.", "error")
            return render_template("register.html", nom=nom, email=email)

        if password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
            return render_template("register.html", nom=nom, email=email)

        if len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
            return render_template("register.html", nom=nom, email=email)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.password_hash:
                flash("Un compte existe déjà avec cette adresse e-mail. Veuillez vous connecter.", "error")
                return redirect(url_for("login"))
            else:
                # L'utilisateur avait été invité au préalable : on active son compte
                existing_user.nom = nom
                existing_user.set_password(password)
                db.session.commit()
                login_user(existing_user)
                flash("Votre compte a été activé avec succès ! Vos invitations vous attendent.", "success")
                return redirect(url_for("index"))

        # Nouvel utilisateur
        new_user = User(nom=nom, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash("Inscription réussie ! Bienvenue sur Todo Fac.", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Identifiants incorrects. Veuillez vérifier votre email et mot de passe.", "error")
            return render_template("login.html", email=email)

        login_user(user, remember=True)
        flash(f"Ravi de vous revoir, {user.nom} !", "success")
        next_page = request.args.get("next")
        return redirect(next_page if next_page else url_for("index"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté(e) avec succès.", "info")
    return redirect(url_for("login"))


# --- TABLEAU DE BORD & GESTION DES PROJETS ---

@app.route("/")
@login_required
def index():
    # Projets dont l'utilisateur connecté est l'administrateur
    projets_administres = (
        Projet.query.filter_by(admin_id=current_user.id)
        .order_by(Projet.date_creation.desc())
        .all()
    )

    # Invitations en attente pour l'utilisateur
    invitations_en_attente = [
        inv for inv in current_user.participations if inv.statut == "en_attente"
    ]

    # Projets rejoints (invitations acceptées)
    participations_acceptees = [
        inv for inv in current_user.participations if inv.statut == "accepte"
    ]

    return render_template(
        "index.html",
        projets_administres=projets_administres,
        invitations_en_attente=invitations_en_attente,
        participations_acceptees=participations_acceptees,
    )


@app.route("/creer_projet", methods=["POST"])
@login_required
def creer_projet():
    titre = request.form.get("titre", "").strip()
    description = request.form.get("description", "").strip()
    emails_invites = request.form.get("emails", "").strip()

    if not titre:
        flash("Le titre du projet est obligatoire.", "error")
        return redirect(url_for("index"))

    # Création du projet (l'admin est automatiquement current_user)
    nouveau_projet = Projet(
        titre=titre,
        description=description,
        admin_id=current_user.id,
    )
    db.session.add(nouveau_projet)
    db.session.commit()

    # Traitement des invitations
    invitations_envoyees = 0
    if emails_invites:
        liste_emails = [e.strip().lower() for e in emails_invites.split(",") if e.strip()]
        # Dédoublonnage des emails
        liste_emails = list(dict.fromkeys(liste_emails))

        for email in liste_emails:
            # Ne pas s'inviter soi-même
            if email == current_user.email:
                continue

            # Trouver ou pré-créer le compte utilisateur
            user_cible = User.query.filter_by(email=email).first()
            if not user_cible:
                user_cible = User(nom=email.split("@")[0], email=email)
                db.session.add(user_cible)
                db.session.commit()

            # Vérifier si déjà invité
            invitation_existante = Invitation.query.filter_by(
                projet_id=nouveau_projet.id, user_id=user_cible.id
            ).first()

            if not invitation_existante:
                invit = Invitation(
                    projet_id=nouveau_projet.id,
                    user_id=user_cible.id,
                    statut="en_attente",
                )
                db.session.add(invit)
                invitations_envoyees += 1

                # Envoi d'email via le service Posta
                send_invitation_email(
                    destinataire_email=user_cible.email,
                    projet_titre=nouveau_projet.titre,
                    admin_nom=current_user.nom,
                    invite_url=url_for("index", _external=True),
                )

        db.session.commit()

    msg = f"Devoir '{titre}' créé avec succès !"
    if invitations_envoyees > 0:
        msg += f" {invitations_envoyees} invitation(s) envoyée(s) par email."
    flash(msg, "success")

    return redirect(url_for("index"))


@app.route("/accepter_invitation/<int:invit_id>", methods=["POST"])
@login_required
def accepter_invitation(invit_id):
    invit = db.session.get(Invitation, invit_id)
    if not invit:
        abort(404)

    # Vérification de sécurité : seul l'invité peut accepter son invitation
    if invit.user_id != current_user.id:
        abort(403)

    invit.statut = "accepte"
    db.session.commit()
    flash(f"Vous avez rejoint le projet '{invit.projet.titre}' avec succès !", "success")
    return redirect(url_for("index"))


@app.route("/refuser_invitation/<int:invit_id>", methods=["POST"])
@login_required
def refuser_invitation(invit_id):
    invit = db.session.get(Invitation, invit_id)
    if not invit:
        abort(404)

    if invit.user_id != current_user.id:
        abort(403)

    db.session.delete(invit)
    db.session.commit()
    flash(f"Invitation au projet '{invit.projet.titre}' refusée.", "info")
    return redirect(url_for("index"))


@app.route("/supprimer_projet/<int:projet_id>", methods=["POST"])
@login_required
def supprimer_projet(projet_id):
    projet = db.session.get(Projet, projet_id)
    if not projet:
        abort(404)

    if projet.admin_id != current_user.id:
        abort(403)

    db.session.delete(projet)
    db.session.commit()
    flash(f"Projet '{projet.titre}' supprimé avec succès.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)