import os
import sys
import json
import html
import unicodedata
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

TOKEN = os.getenv("HESPRESS_TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "689274691")

HISTORIQUE_FILE = "historique_hespress.txt"
DAILY_JSON_FILE = "articles_du_jour.json"

URLS = [
    "https://fr.hespress.com",
    "https://fr.hespress.com/politique",
    "https://fr.hespress.com/economie",
    "https://fr.hespress.com/regions",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    )
}

KEYWORDS = {
    "DGSN": [
        "dgsn", "surete nationale", "police", "commissaire", "brigade", "securite"
    ],
    "BUDGET": [
        "plf", "loi de finances", "budget", "2027", "lekjaa", "finances", "impot", "fiscalite"
    ],
    "INTERIEUR": [
        "ministere de l'interieur", "interieur", "wali", "walis",
        "gouverneur", "gouverneurs", "caid", "caids",
        "administration territoriale", "collectivites territoriales"
    ],
}


def normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


def send_telegram(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print("❌ HESPRESS_TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID manquant.")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            print(f"❌ Erreur Telegram ({r.status_code}): {r.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ Exception Telegram: {e}")
        return False


def load_historique() -> set:
    if not os.path.exists(HISTORIQUE_FILE):
        return set()
    with open(HISTORIQUE_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_historique(urls: set) -> None:
    with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
        for u in sorted(urls):
            f.write(u + "\n")


def load_daily_articles() -> list:
    if not os.path.exists(DAILY_JSON_FILE):
        return []
    try:
        with open(DAILY_JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_daily_articles(articles: list) -> None:
    with open(DAILY_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def match_keyword(text: str):
    norm_text = normalize(text)
    for category, kw_list in KEYWORDS.items():
        for kw in kw_list:
            if kw in norm_text:
                return category, kw
    return None, None


def extract_article_summary(article_url: str, fallback_title: str) -> str:
    try:
        resp = requests.get(article_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return fallback_title
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = soup.select("div.article-content p, article p")
        clean_paras = [
            p.get_text(" ", strip=True)
            for p in paragraphs
            if len(p.get_text(strip=True)) > 45
        ]
        if not clean_paras:
            return fallback_title
        summary = " ".join(clean_paras[:2])
        if len(summary) > 220:
            summary = summary[:217].rsplit(" ", 1)[0] + "..."
        return summary
    except Exception:
        return fallback_title


def run_realtime() -> None:
    print("🔍 Analyse Hespress en cours (Veille rapide)...")
    historique = load_historique()
    daily_articles = load_daily_articles()
    existing_daily_urls = {item["url"] for item in daily_articles}

    maroc_tz = timezone(timedelta(hours=1))
    now_str = datetime.now(maroc_tz).strftime("%H:%M")

    found_count = 0

    for page_url in URLS:
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"⚠️ Accès impossible à {page_url} ({resp.status_code})")
                continue
        except Exception as e:
            print(f"⚠️ Erreur réseau sur {page_url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(" ", strip=True)

            if not href.startswith("https://fr.hespress.com/") or not href.endswith(".html"):
                continue
            if len(title) < 25 or href in historique:
                continue

            category, matched_kw = match_keyword(f"{title} {href}")
            if not category:
                continue

            print(f"📰 [{category}] ({matched_kw}) Article détecté : {title}")
            summary = extract_article_summary(href, title)

            safe_title = html.escape(title)
            safe_summary = html.escape(summary)
            safe_kw = html.escape(matched_kw)

            msg = (
                f"🚨 <b>ALERTE HESPRESS [{category}]</b>\n"
                f"🔑 <b>Mot-clé :</b> <code>{safe_kw}</code> | 🕒 {now_str}\n\n"
                f"📌 <b>{safe_title}</b>\n"
                f"📝 <i>{safe_summary}</i>\n\n"
                f"🔗 <a href=\"{href}\">Lire l'article complet</a>"
            )

            if send_telegram(msg):
                historique.add(href)
                found_count += 1
                if href not in existing_daily_urls:
                    daily_articles.append({
                        "heure": now_str,
                        "axe": category,
                        "mot_cle": matched_kw,
                        "titre": title,
                        "resume": summary,
                        "url": href,
                    })
                    existing_daily_urls.add(href)

    save_historique(historique)
    save_daily_articles(daily_articles)

    if found_count == 0:
        print("ℹ️ Aucun nouvel article correspondant détecté.")
    else:
        print(f"✅ {found_count} nouvelle(s) alerte(s) envoyée(s).")


def run_digest() -> None:
    print("📊 Génération du tableau de synthèse de 03h00...")
    daily_articles = load_daily_articles()

    maroc_tz = timezone(timedelta(hours=1))
    date_str = datetime.now(maroc_tz).strftime("%d/%m/%Y")

    if not daily_articles:
        msg = (
            f"🌙 <b>SYNTHÈSE VEILLE HESPRESS — {date_str} (03h00)</b>\n\n"
            f"ℹ️ Aucune nouvelle publication sur tes axes (DGSN / Budget / Intérieur) durant ce cycle."
        )
        send_telegram(msg)
        return

    header = (
        f"🌙 <b>TABLEAU DE SYNTHÈSE HESPRESS — {date_str} (03h00)</b>\n"
        f"📊 <b>Total :</b> {len(daily_articles)} actualité(s) retenue(s)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    blocks = []
    for idx, item in enumerate(daily_articles, start=1):
        axe = html.escape(item.get("axe", ""))
        kw = html.escape(item.get("mot_cle", ""))
        heure = html.escape(item.get("heure", ""))
        titre = html.escape(item.get("titre", ""))
        resume = html.escape(item.get("resume", ""))
        url = item.get("url", "")

        block = (
            f"<b>#{idx} | [{axe}] • Mot-clé :</b> <code>{kw}</code> ({heure})\n"
            f"📰 <b>Info :</b> {titre}\n"
            f"📝 <b>Résumé :</b> {resume}\n"
            f"🔗 <a href=\"{url}\">Source Hespress</a>\n"
            f"────────────────────\n"
        )
        blocks.append(block)

    current_msg = header
    all_sent = True
    for block in blocks:
        if len(current_msg) + len(block) > 3800:
            if not send_telegram(current_msg):
                all_sent = False
            current_msg = block
        else:
            current_msg += block

    if current_msg.strip():
        if not send_telegram(current_msg):
            all_sent = False

    if all_sent:
        save_daily_articles([])
        print("✅ Tableau de synthèse envoyé et fichier tampon réinitialisé.")
    else:
        print("⚠️ Échec partiel de l'envoi ; conservation des articles dans le fichier tampon.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "realtime"
    if mode == "digest":
        run_digest()
    else:
        run_realtime()
