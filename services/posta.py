import os
import requests
import logging

# Configuration de l'API Posta
POSTA_API_URL = os.environ.get("POSTA_API_URL", "https://api.posta.tech/v1/send")
POSTA_API_KEY = os.environ.get("POSTA_API_KEY", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("posta_service")


def send_invitation_email(destinataire_email, projet_titre, admin_nom, invite_url=None):
    """
    Envoie un email d'invitation à collaborer sur un projet via l'API de l'outil Posta.
    
    Args:
        destinataire_email (str): Adresse email de l'invité.
        projet_titre (str): Titre du devoir/projet.
        admin_nom (str): Nom de l'utilisateur qui invite.
        invite_url (str, optional): Lien direct pour accéder à la plateforme.
        
    Returns:
        bool: True si l'envoi a réussi (ou simulation réussie), False en cas d'erreur.
    """
    subject = f"🎓 Invitation à collaborer sur le projet : {projet_titre}"
    
    body = (
        f"Bonjour,\n\n"
        f"{admin_nom} vous a invité(e) à collaborer sur le devoir universitaire : '{projet_titre}'.\n\n"
    )
    if invite_url:
        body += f"Connectez-vous dès maintenant pour accepter l'invitation :\n{invite_url}\n\n"
    else:
        body += "Connectez-vous à votre espace Todo Fac pour accepter l'invitation.\n\n"
        
    body += "À bientôt sur Todo Fac !"

    # Si aucune clé API n'est configurée (environnement de développement/test)
    if not POSTA_API_KEY:
        logger.info(
            "[POSTA DEV MOCK] Email simulé avec succès vers %s pour le projet '%s' (Admin: %s)",
            destinataire_email,
            projet_titre,
            admin_nom,
        )
        return True

    payload = {
        "to": destinataire_email,
        "subject": subject,
        "text": body,
        "from": os.environ.get("POSTA_FROM_EMAIL", "notifications@todofac.univ.fr"),
    }

    headers = {
        "Authorization": f"Bearer {POSTA_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(POSTA_API_URL, json=payload, headers=headers, timeout=5)
        response.raise_for_status()
        logger.info("[POSTA] Invitation envoyée avec succès à %s", destinataire_email)
        return True
    except requests.exceptions.RequestException as e:
        logger.error("[POSTA ERROR] Échec de l'envoi de l'invitation à %s: %s", destinataire_email, e)
        return False
