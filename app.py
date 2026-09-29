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


# --- INJECTION GLOBALE DE VARIABLES POUR LES TEMPLATES ---
@app.context_processor
def inject_globals():
    if current_user.is_authenticated:
        pending_count = Invitation.query.filter_by(
            user_id=current_user.id, statut="en_attente"
        ).count()
        return {"pending_invitations_count": pending_count}
    return {"pending_invitations_count": 0}


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

    @property
    def total_taches(self):
        return len(self.taches)

    @property
    def taches_terminees(self):
        return len([t for t in self.taches if t.statut == "termine"])

    @property
    def taches_en_cours(self):
        return len([t for t in self.taches if t.statut == "en_cours"])

    @property
    def taches_a_faire(self):
        return len([t for t in self.taches if t.statut == "a_faire"])

    @property
    def pourcentage_progression(self):
        if not self.taches:
            return 0
        return int(round((self.taches_terminees / len(self.taches)) * 100))

    def membres_actifs(self):
        """Retourne les membres pouvant recevoir des tâches : admin + invités acceptés."""
        membres = [self.admin]
        for inv in self.invitations:
            if inv.statut == "accepte" and inv.user not in membres:
                membres.append(inv.user)
        return membres

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


class Tache(db.Model):
    __tablename__ = "tache"

    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    statut = db.Column(db.String(30), default="a_faire")  # 'a_faire', 'en_cours', 'termine'
    priorite = db.Column(db.String(20), default="moyenne")  # 'basse', 'moyenne', 'haute'
    date_echeance = db.Column(db.Date, nullable=True)

    # Auteur et assignation
    createur_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assigne_a_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    date_creation = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    date_mise_a_jour = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relations
    projet = db.relationship(
        "Projet",
        backref=db.backref("taches", lazy=True, cascade="all, delete-orphan", order_by="Tache.date_creation.desc()"),
    )
    createur = db.relationship("User", foreign_keys=[createur_id], backref="taches_creees")
    assigne_a = db.relationship("User", foreign_keys=[assigne_a_id], backref="taches_assignees")

    def __repr__(self):
        return f"<Tache {self.titre} ({self.statut})>"


with app.app_context():
    db.create_all()


# --- HELPER DE PERMISSION ---
def verifier_acces_projet(projet_id, user_id):
    """Vérifie si l'utilisateur a accès au devoir (Admin ou Membre actif). Retourne (projet, is_admin)."""
    projet = db.session.get(Projet, projet_id)
    if not projet:
        abort(404)

    if projet.admin_id == user_id:
        return projet, True

    invit = Invitation.query.filter_by(
        projet_id=projet_id, user_id=user_id, statut="accepte"
    ).first()
    if invit:
        return projet, False

    abort(403)


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
                existing_user.nom = nom
                existing_user.set_password(password)
                db.session.commit()
                login_user(existing_user)
                flash("Votre compte a été activé avec succès ! Vos invitations vous attendent.", "success")
                return redirect(url_for("index"))

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


# --- 1. TABLEAU DE BORD (ACCUEIL) ---

@app.route("/")
@login_required
def index():
    projets_administres = (
        Projet.query.filter_by(admin_id=current_user.id)
        .order_by(Projet.date_creation.desc())
        .all()
    )

    invitations_en_attente = [
        inv for inv in current_user.participations if inv.statut == "en_attente"
    ]

    participations_acceptees = [
        inv for inv in current_user.participations if inv.statut == "accepte"
    ]

    collab_ids = set()
    for p in projets_administres:
        for inv in p.invitations:
            if inv.user_id != current_user.id:
                collab_ids.add(inv.user_id)
    for part in participations_acceptees:
        if part.projet.admin_id != current_user.id:
            collab_ids.add(part.projet.admin_id)
        for inv in part.projet.invitations:
            if inv.user_id != current_user.id:
                collab_ids.add(inv.user_id)

    total_collaborateurs = len(collab_ids)

    return render_template(
        "index.html",
        projets_administres=projets_administres,
        invitations_en_attente=invitations_en_attente,
        participations_acceptees=participations_acceptees,
        total_collaborateurs=total_collaborateurs,
    )


# --- 2. PAGE SÉPARÉE : CRÉER UN DEVOIR ---

@app.route("/creer-devoir", methods=["GET", "POST"])
@login_required
def creer_devoir():
    if request.method == "POST":
        titre = request.form.get("titre", "").strip()
        description = request.form.get("description", "").strip()
        emails_invites = request.form.get("emails", "").strip()

        if not titre:
            flash("Le titre du devoir est obligatoire.", "error")
            return render_template("creer_devoir.html")

        nouveau_projet = Projet(
            titre=titre,
            description=description,
            admin_id=current_user.id,
        )
        db.session.add(nouveau_projet)
        db.session.commit()

        invitations_envoyees = 0
        if emails_invites:
            liste_emails = [e.strip().lower() for e in emails_invites.split(",") if e.strip()]
            liste_emails = list(dict.fromkeys(liste_emails))

            for email in liste_emails:
                if email == current_user.email:
                    continue

                user_cible = User.query.filter_by(email=email).first()
                if not user_cible:
                    user_cible = User(nom=email.split("@")[0], email=email)
                    db.session.add(user_cible)
                    db.session.commit()

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

                    send_invitation_email(
                        destinataire_email=user_cible.email,
                        projet_titre=nouveau_projet.titre,
                        admin_nom=current_user.nom,
                        invite_url=url_for("devoirs_partages", _external=True),
                    )

            db.session.commit()

        msg = f"Devoir '{titre}' créé avec succès !"
        if invitations_envoyees > 0:
            msg += f" {invitations_envoyees} invitation(s) transmise(s) par email."
        flash(msg, "success")

        return redirect(url_for("detail_projet", projet_id=nouveau_projet.id))

    return render_template("creer_devoir.html")


@app.route("/creer_projet", methods=["POST"])
@login_required
def creer_projet():
    """Alias pour compatibilité."""
    return creer_devoir()


# --- 3. PAGE SÉPARÉE : MES DEVOIRS ---

@app.route("/mes-devoirs")
@login_required
def mes_devoirs():
    projets = (
        Projet.query.filter_by(admin_id=current_user.id)
        .order_by(Projet.date_creation.desc())
        .all()
    )
    return render_template("mes_devoirs.html", projets=projets)


# --- 4. PAGE SÉPARÉE : DEVOIRS PARTAGÉS ---

@app.route("/devoirs-partages")
@login_required
def devoirs_partages():
    invitations_en_attente = [
        inv for inv in current_user.participations if inv.statut == "en_attente"
    ]
    participations_acceptees = [
        inv for inv in current_user.participations if inv.statut == "accepte"
    ]
    return render_template(
        "devoirs_partages.html",
        invitations_en_attente=invitations_en_attente,
        participations_acceptees=participations_acceptees,
    )


# --- 5. PAGE SÉPARÉE : LISTES DE COLLABORATEURS ---

@app.route("/collaborateurs")
@login_required
def collaborateurs():
    mes_projets = (
        Projet.query.filter_by(admin_id=current_user.id)
        .order_by(Projet.date_creation.desc())
        .all()
    )

    participations_acceptees = [
        inv for inv in current_user.participations if inv.statut == "accepte"
    ]

    collabs = {}

    for p in mes_projets:
        for invit in p.invitations:
            u = invit.user
            if u.id == current_user.id:
                continue
            if u.id not in collabs:
                collabs[u.id] = {
                    "user": u,
                    "projets": [],
                    "has_active": False,
                    "has_pending": False,
                }
            collabs[u.id]["projets"].append({
                "projet": p,
                "statut": invit.statut,
                "role": "admin",
                "invitation_id": invit.id,
            })
            if invit.statut == "accepte":
                collabs[u.id]["has_active"] = True
            elif invit.statut == "en_attente":
                collabs[u.id]["has_pending"] = True

    for part in participations_acceptees:
        proj = part.projet
        admin_u = proj.admin
        if admin_u.id != current_user.id:
            if admin_u.id not in collabs:
                collabs[admin_u.id] = {
                    "user": admin_u,
                    "projets": [],
                    "has_active": True,
                    "has_pending": False,
                }
            if not any(r["projet"].id == proj.id for r in collabs[admin_u.id]["projets"]):
                collabs[admin_u.id]["projets"].append({
                    "projet": proj,
                    "statut": "accepte",
                    "role": "admin_du_projet",
                    "invitation_id": None,
                })

        for other_invit in proj.invitations:
            ou = other_invit.user
            if ou.id != current_user.id:
                if ou.id not in collabs:
                    collabs[ou.id] = {
                        "user": ou,
                        "projets": [],
                        "has_active": other_invit.statut == "accepte",
                        "has_pending": other_invit.statut == "en_attente",
                    }
                if not any(r["projet"].id == proj.id for r in collabs[ou.id]["projets"]):
                    collabs[ou.id]["projets"].append({
                        "projet": proj,
                        "statut": other_invit.statut,
                        "role": "membre",
                        "invitation_id": other_invit.id,
                    })
                if other_invit.statut == "accepte":
                    collabs[ou.id]["has_active"] = True
                elif other_invit.statut == "en_attente":
                    collabs[ou.id]["has_pending"] = True

    collaborateurs_liste = list(collabs.values())
    collaborateurs_liste.sort(key=lambda x: x["user"].nom.lower())

    return render_template(
        "collaborateurs.html",
        collaborateurs_liste=collaborateurs_liste,
        mes_projets=mes_projets,
    )


# --- 6. ESPACE DE COLLABORATION & TÂCHES D'UN DEVOIR ---

@app.route("/devoir/<int:projet_id>")
@login_required
def detail_projet(projet_id):
    projet, is_admin = verifier_acces_projet(projet_id, current_user.id)
    membres = projet.membres_actifs()

    # Statistiques et progression par membre
    stats_membres = []
    for m in membres:
        t_m = [t for t in projet.taches if t.assigne_a_id == m.id]
        done = len([t for t in t_m if t.statut == "termine"])
        in_progress = len([t for t in t_m if t.statut == "en_cours"])
        todo = len([t for t in t_m if t.statut == "a_faire"])
        stats_membres.append({
            "user": m,
            "total": len(t_m),
            "done": done,
            "in_progress": in_progress,
            "todo": todo,
            "is_admin": m.id == projet.admin_id,
            "progression": int(round((done / len(t_m)) * 100)) if t_m else 0,
        })

    # Tâches non assignées
    taches_non_assignees = [t for t in projet.taches if t.assigne_a_id is None]

    # Découpage des tâches par statut
    taches_a_faire = [t for t in projet.taches if t.statut == "a_faire"]
    taches_en_cours = [t for t in projet.taches if t.statut == "en_cours"]
    taches_terminees = [t for t in projet.taches if t.statut == "termine"]

    return render_template(
        "detail_devoir.html",
        projet=projet,
        is_admin=is_admin,
        membres=membres,
        stats_membres=stats_membres,
        taches_non_assignees=taches_non_assignees,
        taches_a_faire=taches_a_faire,
        taches_en_cours=taches_en_cours,
        taches_terminees=taches_terminees,
    )


@app.route("/devoir/<int:projet_id>/ajouter_tache", methods=["POST"])
@login_required
def ajouter_tache(projet_id):
    projet, is_admin = verifier_acces_projet(projet_id, current_user.id)

    titre = request.form.get("titre", "").strip()
    description = request.form.get("description", "").strip()
    priorite = request.form.get("priorite", "moyenne").strip().lower()
    assigne_a_id = request.form.get("assigne_a_id", type=int)
    date_str = request.form.get("date_echeance", "").strip()

    if not titre:
        flash("Le titre de la tâche est obligatoire.", "error")
        return redirect(url_for("detail_projet", projet_id=projet_id))

    date_echeance = None
    if date_str:
        try:
            date_echeance = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            date_echeance = None

    # Vérification que l'assigné est bien membre actif du projet
    if assigne_a_id:
        membres_ids = [m.id for m in projet.membres_actifs()]
        if assigne_a_id not in membres_ids:
            assigne_a_id = None

    nouvelle_tache = Tache(
        projet_id=projet.id,
        titre=titre,
        description=description,
        priorite=priorite if priorite in ["basse", "moyenne", "haute"] else "moyenne",
        date_echeance=date_echeance,
        createur_id=current_user.id,
        assigne_a_id=assigne_a_id,
        statut="a_faire",
    )
    db.session.add(nouvelle_tache)
    db.session.commit()

    flash(f"Tâche '{titre}' ajoutée avec succès au devoir !", "success")
    return redirect(url_for("detail_projet", projet_id=projet_id))


@app.route("/tache/<int:tache_id>/changer_statut", methods=["POST"])
@login_required
def changer_statut_tache(tache_id):
    tache = db.session.get(Tache, tache_id)
    if not tache:
        abort(404)

    # Vérifier l'accès au projet de la tâche
    verifier_acces_projet(tache.projet_id, current_user.id)

    nouveau_statut = request.form.get("nouveau_statut", "").strip()
    if nouveau_statut in ["a_faire", "en_cours", "termine"]:
        tache.statut = nouveau_statut
        db.session.commit()
        labels = {
            "a_faire": "À faire 📋",
            "en_cours": "En cours ⏳",
            "termine": "Terminé ✅",
        }
        flash(f"Statut de '{tache.titre}' mis à jour : {labels.get(nouveau_statut)}", "info")

    return redirect(request.referrer or url_for("detail_projet", projet_id=tache.projet_id))


@app.route("/tache/<int:tache_id>/assigner", methods=["POST"])
@login_required
def assigner_tache(tache_id):
    tache = db.session.get(Tache, tache_id)
    if not tache:
        abort(404)

    projet, is_admin = verifier_acces_projet(tache.projet_id, current_user.id)

    assigne_a_id = request.form.get("assigne_a_id", type=int)
    if assigne_a_id:
        membres_ids = [m.id for m in projet.membres_actifs()]
        if assigne_a_id in membres_ids:
            tache.assigne_a_id = assigne_a_id
        else:
            tache.assigne_a_id = None
    else:
        tache.assigne_a_id = None

    db.session.commit()
    flash(f"Affectation de la tâche '{tache.titre}' mise à jour !", "success")
    return redirect(request.referrer or url_for("detail_projet", projet_id=tache.projet_id))


@app.route("/tache/<int:tache_id>/supprimer", methods=["POST"])
@login_required
def supprimer_tache(tache_id):
    tache = db.session.get(Tache, tache_id)
    if not tache:
        abort(404)

    projet, is_admin = verifier_acces_projet(tache.projet_id, current_user.id)

    # Seuls l'admin du projet ou le créateur de la tâche peuvent supprimer
    if not is_admin and tache.createur_id != current_user.id:
        abort(403)

    titre = tache.titre
    projet_id = tache.projet_id
    db.session.delete(tache)
    db.session.commit()

    flash(f"Tâche '{titre}' supprimée.", "info")
    return redirect(request.referrer or url_for("detail_projet", projet_id=projet_id))


# --- ACTIONS SUR LES INVITATIONS & COLLABORATEURS ---

@app.route("/inviter_collaborateur/<int:projet_id>", methods=["POST"])
@login_required
def inviter_collaborateur(projet_id):
    projet = db.session.get(Projet, projet_id)
    if not projet:
        abort(404)
    if projet.admin_id != current_user.id:
        abort(403)

    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Veuillez renseigner une adresse email valide.", "error")
        return redirect(request.referrer or url_for("mes_devoirs"))

    if email == current_user.email:
        flash("Vous ne pouvez pas vous inviter vous-même.", "warning")
        return redirect(request.referrer or url_for("mes_devoirs"))

    user_cible = User.query.filter_by(email=email).first()
    if not user_cible:
        user_cible = User(nom=email.split("@")[0], email=email)
        db.session.add(user_cible)
        db.session.commit()

    invit = Invitation.query.filter_by(projet_id=projet.id, user_id=user_cible.id).first()
    if invit:
        flash(f"{user_cible.nom} est déjà invité(e) sur ce devoir (statut : {invit.statut}).", "info")
    else:
        invit = Invitation(projet_id=projet.id, user_id=user_cible.id, statut="en_attente")
        db.session.add(invit)
        db.session.commit()
        send_invitation_email(
            destinataire_email=user_cible.email,
            projet_titre=projet.titre,
            admin_nom=current_user.nom,
            invite_url=url_for("devoirs_partages", _external=True),
        )
        flash(f"Invitation transmise avec succès à {user_cible.email} !", "success")

    return redirect(request.referrer or url_for("mes_devoirs"))


@app.route("/inviter_collaborateur_generique", methods=["POST"])
@login_required
def inviter_collaborateur_generique():
    projet_id = request.form.get("projet_id", type=int)
    if not projet_id:
        flash("Veuillez sélectionner un devoir.", "error")
        return redirect(url_for("collaborateurs"))
    return inviter_collaborateur(projet_id)


@app.route("/relancer_invitation/<int:invit_id>", methods=["POST"])
@login_required
def relancer_invitation(invit_id):
    invit = db.session.get(Invitation, invit_id)
    if not invit:
        abort(404)
    if invit.projet.admin_id != current_user.id:
        abort(403)

    send_invitation_email(
        destinataire_email=invit.user.email,
        projet_titre=invit.projet.titre,
        admin_nom=current_user.nom,
        invite_url=url_for("devoirs_partages", _external=True),
    )
    flash(f"L'invitation pour {invit.user.email} a été relancée par e-mail.", "success")
    return redirect(request.referrer or url_for("mes_devoirs"))


@app.route("/supprimer_collaborateur/<int:invit_id>", methods=["POST"])
@login_required
def supprimer_collaborateur(invit_id):
    invit = db.session.get(Invitation, invit_id)
    if not invit:
        abort(404)
    if invit.projet.admin_id != current_user.id:
        abort(403)

    user_nom = invit.user.nom
    db.session.delete(invit)
    db.session.commit()
    flash(f"{user_nom} a été retiré(e) du devoir.", "info")
    return redirect(request.referrer or url_for("mes_devoirs"))


@app.route("/accepter_invitation/<int:invit_id>", methods=["POST"])
@login_required
def accepter_invitation(invit_id):
    invit = db.session.get(Invitation, invit_id)
    if not invit:
        abort(404)

    if invit.user_id != current_user.id:
        abort(403)

    invit.statut = "accepte"
    db.session.commit()
    flash(f"Vous avez rejoint le devoir '{invit.projet.titre}' avec succès !", "success")
    return redirect(url_for("detail_projet", projet_id=invit.projet_id))


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
    flash(f"Invitation au devoir '{invit.projet.titre}' déclinée.", "info")
    return redirect(url_for("devoirs_partages"))


@app.route("/quitter_projet/<int:invit_id>", methods=["POST"])
@login_required
def quitter_projet(invit_id):
    invit = db.session.get(Invitation, invit_id)
    if not invit:
        abort(404)

    if invit.user_id != current_user.id:
        abort(403)

    projet_titre = invit.projet.titre
    db.session.delete(invit)
    db.session.commit()
    flash(f"Vous vous êtes retiré(e) du devoir '{projet_titre}'.", "info")
    return redirect(url_for("devoirs_partages"))


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
    flash(f"Devoir '{projet.titre}' supprimé avec succès.", "success")
    return redirect(request.referrer or url_for("mes_devoirs"))


if __name__ == "__main__":
    app.run(debug=True)