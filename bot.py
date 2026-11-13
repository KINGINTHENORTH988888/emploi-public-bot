import requests
from bs4 import BeautifulSoup
import os

TOKEN = os.environ.get("TELEGRAM_TOKEN", "9121764120:AAHHWMED8OY1fhUZn2CnXCyMw0zXjysLUOQ")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "689274691")

def envoyer_alerte(titre_offre, lien_offre):
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
    print("🔍 Analyse élargie des pages de concours en cours...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    trouve_global = 0
    
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
                    texte_lower = texte_offre.lower()
                    
                    contient_admin = "administrateur" in texte_lower
                    contient_grade = ("2e grade" in texte_lower or "2ème grade" in texte_lower or 
                                      "echelle 11" in texte_lower or "échelle 11" in texte_lower)
                    
                    if contient_admin and contient_grade:
                        if href.startswith('http'):
                            lien_offre = href
                        else:
                            lien_offre = "https://www.emploi-public.ma" + href
                            
                        print(f"🎯 [Page {page_num}] Offre cible trouvée : {texte_offre}")
                        succes = envoyer_alerte(texte_offre, lien_offre)
                        if succes:
                            print("🚀 Alerte envoyée avec succès sur ton Telegram !")
                        trouve_global += 1
            else:
                print(f"❌ Impossible d'accéder à la page {page_num}")
                
        except Exception as e:
            print(f"Erreur sur la page {page_num} : {e}")
            
    if trouve_global == 0:
        print("ℹ️ Aucun poste d'Administrateur 2ème grade / Échelle 11 trouvé.")

if __name__ == "__main__":
    verifier_toutes_les_pages()
