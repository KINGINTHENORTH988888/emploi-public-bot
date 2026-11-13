import requests
from bs4 import BeautifulSoup
import os

TOKEN = os.environ.get("TELEGRAM_TOKEN", "9121764120:AAHHWMED8OY1fhUZn2CnXCyMw0zXjysLUOQ")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "689274691")
FICHIER_HISTORIQUE = "historique.txt"

def charger_historique():
    if not os.path.exists(FICHIER_HISTORIQUE):
        return set()
    with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def sauvegarder_historique(liens_vus):
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        for lien in liens_vus:
            f.write(lien + "\n")

def envoyer_alerte(titre_offre, lien_offre):
    message = (
        "🎯 **NOUVEAU CONCOURS DÉTECTÉ !**\n\n"
        f"• **Intitulé :** {titre_offre}\n\n"
        "✅ *Correspondance : Administrateur 2ème grade / Échelle 11*"
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

def verifier_offres():
    print("🔍 Recherche des NOUVELLES offres Administrateur 2e grade...")
    liens_vus = charger_historique()
    nouveaux_ajouts = False
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    url_site = "https://www.emploi-public.ma/fr/concours-liste?page=1"
    
    try:
        response = requests.get(url_site, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            liens = soup.find_all('a', href=True)
            
            trouve = 0
            for l in liens:
                href = l['href']
                texte_offre = l.get_text().strip()
                
                if len(texte_offre) < 10:
                    continue
                    
                texte_lower = texte_offre.lower()
                
                if "administrateur" in texte_lower and ("2e grade" in texte_lower or "2ème grade" in texte_lower or "echelle 11" in texte_lower or "échelle 11" in texte_lower):
                    lien_complet = href if href.startswith('http') else "https://www.emploi-public.ma" + href
                    
                    # Vérification anti-doublon
                    if lien_complet in liens_vus:
                        print(f"⏭️ Déjà envoyé : {texte_offre}")
                        continue
                        
                    print(f"🎯 Nouvelle offre trouvée : {texte_offre}")
                    if envoyer_alerte(texte_offre, lien_complet):
                        print("🚀 Alerte envoyée sur Telegram !")
                        liens_vus.add(lien_complet)
                        nouveaux_ajouts = True
                    trouve += 1
                    
            if nouveaux_ajouts:
                sauvegarder_historique(liens_vus)
                print("💾 Historique mis à jour.")
            elif trouve == 0:
                print("ℹ️ Aucune nouvelle offre à signaler.")
        else:
            print("❌ Erreur d'accès au site.")
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    verifier_offres()
