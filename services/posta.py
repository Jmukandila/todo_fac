import os
import requests
import logging
from dotenv import load_dotenv

# Chargement automatique des variables d'environnement (.env)
load_dotenv()

# Configuration par défaut de l'API Posta
DEFAULT_POSTA_API_URL = "https://api.goposta.dev/api/v1/emails/send"
DEFAULT_POSTA_FROM_EMAIL = "joshkaninda@gmail.com"

POSTA_API_URL = os.environ.get("POSTA_API_URL", DEFAULT_POSTA_API_URL)
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
    load_dotenv()
    api_key = os.environ.get("POSTA_API_KEY", POSTA_API_KEY).strip()
    api_url = os.environ.get("POSTA_API_URL", POSTA_API_URL).strip()
    from_email = os.environ.get("POSTA_FROM_EMAIL", DEFAULT_POSTA_FROM_EMAIL).strip()

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
    if not api_key:
        logger.info(
            "[POSTA DEV MOCK] Email simulé avec succès vers %s pour le projet '%s' (Admin: %s)",
            destinataire_email,
            projet_titre,
            admin_nom,
        )
        return True

    # Génération du contenu HTML stylisé
    action_html = ""
    if invite_url:
        action_html = f"""
        <div style="margin: 25px 0;">
            <a href="{invite_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                Accepter l'invitation
            </a>
        </div>
        """
    else:
        action_html = """
        <p style="color: #64748b; font-size: 14px;">Connectez-vous à votre espace Todo Fac pour accepter l'invitation.</p>
        """

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; padding: 30px; margin: 0;">
    <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; padding: 32px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
        <div style="margin-bottom: 20px;">
            <span style="font-size: 24px; font-weight: 800; color: #0f172a;">Todo<span style="color: #4f46e5;">Fac</span></span>
        </div>
        <h2 style="font-size: 18px; color: #1e293b; margin-top: 0;">Invitation à un devoir collaboratif</h2>
        <p style="color: #334155; font-size: 15px; line-height: 1.6;">Bonjour,</p>
        <p style="color: #334155; font-size: 15px; line-height: 1.6;">
            <strong>{admin_nom}</strong> vous a invité(e) à collaborer sur le devoir universitaire : <strong>« {projet_titre} »</strong>.
        </p>
        {action_html}
        <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 25px 0;">
        <p style="color: #94a3b8; font-size: 12px; margin: 0;">À bientôt sur Todo Fac !</p>
    </div>
</body>
</html>"""

    # L'API Posta attend 'to' sous forme de liste de destinataires
    recipients = [destinataire_email] if isinstance(destinataire_email, str) else list(destinataire_email)

    payload = {
        "to": recipients,
        "subject": subject,
        "text": body,
        "html": html_content,
        "from": from_email,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        if response.status_code >= 400:
            logger.error("[POSTA ERROR] Code %s - Détails : %s", response.status_code, response.text)
        response.raise_for_status()
        logger.info("[POSTA] Invitation envoyée avec succès à %s", destinataire_email)
        return True
    except requests.exceptions.RequestException as e:
        logger.error("[POSTA ERROR] Échec de l'envoi de l'invitation à %s : %s", destinataire_email, e)
        return False
