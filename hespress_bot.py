import os
import re
import unicodedata
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ.get("HESPRESS_TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "689274691")
FICHIER_HISTORIQUE = "historique_hespress.txt"

CATEGORIES = {
    "dgsn": {
        "bandeau": "ACTUALITÉ CIBLÉE DÉTECTÉE\n👮 SÉCURITÉ NATIONALE : NOUVELLE ACTUALITÉ DGSN !",
        "domaine": "DGSN et sécurité nationale",
        "profil": "DGSN / Sécurité publique",
        "pertinence": "5/5",
        "points": [
            "Évolution ou mesure liée à la sûreté et à l'ordre public.",
            "Impact opérationnel ou organisationnel pour les services de police.",
            "À suivre pour l'actualité institutionnelle et sécuritaire.",
        ],
        "mots_cles": [
            "dgsn",
            "sûreté nationale",
            "police nationale",
            "police marocaine",
            "abdellatif hammouchi",
            "police judiciaire",
            "sécurité nationale",
            "commissaire de police",
        ],
    },
    "budget": {
        "bandeau": "ACTUALITÉ CIBLÉE DÉTECTÉE\n💰 ALERTE BUDGÉTAIRE : FINANCES PUBLIQUES & BUDGET !",
        "domaine": "Économie et finances publiques",
        "profil": "Budget de l'État / Finances publiques",
        "pertinence": "5/5",
        "points": [
            "Orientations budgétaires, recettes ou dépenses publiques.",
            "Équilibres macroéconomiques (déficit, dette, fiscalité).",
            "Implications potentielles sur les politiques et investissements publics.",
        ],
        "mots_cles": [
            "loi de finances",
            "projet de loi de finances",
            "plf 2027",
            "budget de l'état",
            "finances publiques",
            "déficit budgétaire",
            "dette publique",
            "dépenses publiques",
            "recettes fiscales",
        ],
    },
    "interieur": {
        "bandeau": "ACTUALITÉ CIBLÉE DÉTECTÉE\n🏛️ ADMINISTRATION TERRITORIALE : MINISTÈRE DE L'INTÉRIEUR !",
        "domaine": "Gouvernance et administration territoriale",
        "profil": "Ministère de l'Intérieur / Territoires",
        "pertinence": "5/5",
        "points": [
            "Décision ou orientation liée à l'administration territoriale.",
            "Rôle des walis, gouverneurs, autorités locales ou collectivités.",
            "Impact sur la gouvernance et la gestion territoriale.",
        ],
        "mots_cles": [
            "ministère de l'intérieur",
            "abdelouafi laftit",
            "administration territoriale",
            "walis",
            "gouverneurs",
            "collectivités territoriales",
            "autorités locales",
            "agents d'autorité",
        ],
    },
}


def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(ch for ch in texte if unicodedata.category(ch) != "Mn")
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def charger_historique() -> set:
    if not os.path.exists(FICHIER_HISTORIQUE):
        return set()
    with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def sauvegarder_historique(liens_vus: set) -> None:
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        for lien in sorted(liens_vus):
            f.write(lien + "\n")


def detecter_categorie(texte_normalise: str):
    for cle, config in CATEGORIES.items():
        matches = []
        for mot in config["mots_cles"]:
            mot_norm = normaliser(mot)
            if len(mot_norm) <= 4 and mot_norm.isalpha():
                if re.search(rf"\b{re.escape(mot_norm)}\b", texte_normalise):
                    matches.append(mot)
            else:
                if mot_norm in texte_normalise:
                    matches.append(mot)
        if matches:
            return cle, config, matches
    return None, None, []


def formater_message(titre: str, lien: str, config: dict, matches: list) -> str:
    points_str = "\n".join(f"- {p}" for p in config["points"])
    mots_str = ", ".join(matches)
    return (
        f"{config['bandeau']}\n"
        f"- Sujet : {titre}\n"
        f"- Domaine : {config['domaine']}\n"
        f"- Mots-clés détectés : {mots_str}\n"
        f"- Points essentiels :\n"
        f"{points_str}\n"
        f"🎯 Pertinence : {config['pertinence']}\n"
        f"✅ Profil validé : {config['profil']}\n"
        f"🔗 Lire l'article : [Hespress]({lien})"
    )


def envoyer_alerte(message: str, lien: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print("❌ HESPRESS_TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID manquant.")
        return False

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "Lire l'article sur Hespress ↗", "url": lien}]
            ]
        },
    }
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, json=payload, timeout=15)
    if r.status_code != 200:
        payload_plain = {
            "chat_id": CHAT_ID,
            "text": message.replace("*", "").replace("[Hespress](", "").replace(")", ""),
        }
        r = requests.post(url, json=payload_plain, timeout=15)
    return r.status_code == 200


def verifier_hespress() -> None:
    print("🔍 Analyse Hespress en cours (DGSN / Budget / Ministère de l'Intérieur)...")
    liens_vus = charger_historique()
    nouveaux_ajouts = False

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
    }

    urls_a_verifier = [
        "https://fr.hespress.com/",
        "https://fr.hespress.com/politique",
        "https://fr.hespress.com/economie",
        "https://fr.hespress.com/regions",
    ]

    for url_page in urls_a_verifier:
        try:
            resp = requests.get(url_page, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"⚠️ Accès impossible ({resp.status_code}) sur {url_page}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                titre = re.sub(r"\s+", " ", a.get_text()).strip()
                if len(titre) < 15:
                    continue

                href = a["href"].strip()
                if href.startswith("/"):
                    lien = "https://fr.hespress.com" + href
                elif href.startswith("http"):
                    lien = href
                else:
                    continue

                if "hespress.com" not in lien or lien in liens_vus:
                    continue

                texte_norm = normaliser(f"{titre} {lien}")
                cle, config, matches = detecter_categorie(texte_norm)

                if config:
                    print(f"📰 [{cle.upper()}] Article détecté : {titre}")
                    msg = formater_message(titre, lien, config, matches)
                    if envoyer_alerte(msg, lien):
                        print("🚀 Notification envoyée sur Telegram !")
                        liens_vus.add(lien)
                        nouveaux_ajouts = True

        except Exception as e:
            print(f"❌ Erreur sur {url_page} : {e}")

    if nouveaux_ajouts:
        sauvegarder_historique(liens_vus)
        print(f"💾 {len(liens_vus)} lien(s) enregistré(s) dans {FICHIER_HISTORIQUE}.")
    else:
        print("ℹ️ Aucun nouvel article correspondant détecté.")


if __name__ == "__main__":
    verifier_hespress()
