import requests
from bs4 import BeautifulSoup
import os

TOKEN = os.environ.get("TELEGRAM_TOKEN", "9121764120:AAHHWMED8OY1fhUZn2CnXCyMw0zXjysLUOQ")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "689274691")

# Liste de mots-clés liés à ton Master (Marketing Stratégique & Management Commercial)
MOTS_CLES_DIPLOME = [
    "marketing", "commercial", "commerce", "management", 
    "stratégie", "strategique", "stratégique", "gestion", 
    "entreprise", "entreprises", "vente", "clientèle", "communication"
]

def envoyer_alerte(titre_offre, lien_offre, est_prioritaire=False, mots_trouves=None):
    if est_prioritaire:
        tags = ", ".join(mots_trouves).upper()
        message = (
            "🚨🔥 **ALERTE HAUTE PRIORITÉ — TON DIPLÔME !** 🔥🚨\n\n"
            f"• **Intitulé :** {titre_offre}\n"
            f"• **Mots-clés détectés :** `{tags}`\n\n"
            "⭐ *Correspondance directe : Master Marketing & Management Commercial*"
        )
    else:
        message = (
            "🎯 **NOUVEAU CONCOURS CIBLÉ DÉTECTÉ !**\n\n"
            f"• **Intitulé :** {titre_offre}\n\n"
            "✅ *Profil validé : Administrateur 2ème grade / Échelle 11*"
        )
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "Consulter l'offre officielle ↗", "url": lien_offre}]
            ]
        }
    }
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    response = requests.post(url, json=payload)
    return response.status_code == 200

def verifier_toutes_les_pages():
    print("🔍 Analyse avancée (Grade + Spécialité Master) en cours...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    trouve_global = 0
    offres_traitees = set() # Évite les doublons
    
    for page_num in range(1, 4):
        url_site = f"https://www.emploi-public.ma/fr/concours-liste?page={page_num}"
        
        try:
            response = requests.get(url_site, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                liens = soup.find_all('a', href=True)
                
                for l in liens:
                    href = l['href']
                    texte_offre = l.get_text().strip()
                    
                    # Ignorer les liens vides ou menus
                    if len(texte_offre) < 10:
                        continue
                        
                    texte_lower = texte_offre.lower()
                    lien_complet = href if href.startswith('http') else "https://www.emploi-public.ma" + href
                    
                    if lien_complet in offres_traitees:
                        continue

                    # 1. Vérification Grade (Administrateur 2e grade / Échelle 11)
                    contient_admin = "administrateur" in texte_lower
                    contient_grade = ("2e grade" in texte_lower or "2ème grade" in texte_lower or 
                                      "echelle 11" in texte_lower or "échelle 11" in texte_lower)
                    est_admin_2e = contient_admin and contient_grade

                    # 2. Vérification Spécialité Diplôme
                    mots_trouves = [mot for mot in MOTS_CLES_DIPLOME if mot in texte_lower]
                    est_specialite = len(mots_trouves) > 0

                    # Déclenchement de l'alerte si l'un ou l'autre correspond
                    if est_admin_2e or est_specialite:
                        offres_traitees.add(lien_complet)
                        
                        if est_specialite:
                            print(f"🚨 [Page {page_num}] OFFRE PRIORITAIRE ({mots_trouves}) : {texte_offre}")
                            succes = envoyer_alerte(texte_offre, lien_complet, est_prioritaire=True, mots_trouves=mots_trouves)
                        else:
                            print(f"🎯 [Page {page_num}] Offre standard trouvée : {texte_offre}")
                            succes = envoyer_alerte(texte_offre, lien_complet, est_prioritaire=False)
                            
                        if succes:
                            print("🚀 Alerte envoyée sur Telegram !")
                        trouve_global += 1
            else:
                print(f"❌ Impossible d'accéder à la page {page_num}")
                
        except Exception as e:
            print(f"Erreur sur la page {page_num} : {e}")
            
    if trouve_global == 0:
        print("ℹ️ Aucune nouvelle offre correspondante trouvée.")

if __name__ == "__main__":
    verifier_toutes_les_pages()
