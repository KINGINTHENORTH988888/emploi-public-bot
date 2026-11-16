import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

URL = "https://fr.hespress.com/"
HISTORY_FILE = "historique_hespress.txt"
DIGEST_FILE = "articles_du_jour.json"

TELEGRAM_TOKEN = os.environ.get("HESPRESS_TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Mots-clés ciblés sans faux positifs ("2027" seul retiré)
KEYWORDS = {
    "DGSN": [
        "dgsn", "surete nationale", "police", "commissaire",
        "brigade", "securite publique"
    ],
    "BUDGET": [
        "plf", "plf 2027", "loi de finances", "budget 2027",
        "budgets 2027", "lekjaa", "finances", "impot", "fiscalite"
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
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.lower()).strip()


def morocco_now() -> datetime:
    # UTC+1 (heure standard Maroc)
    return datetime.now(timezone(timedelta(hours=1)))


def load_history() -> set[str]:
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_history(urls: list[str]) -> None:
    if not urls:
        return
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        for u in urls:
            f.write(u + "\n")


def load_digest_buffer() -> list[dict]:
    if not os.path.exists(DIGEST_FILE):
        return []
    try:
        with open(DIGEST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_digest_buffer(items: list[dict]) -> None:
    with open(DIGEST_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Variables HESPRESS_TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID manquantes.")
        return False
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(api_url, json=payload, timeout=15)
        if not r.ok:
            print(f"❌ Erreur Telegram ({r.status_code}) : {r.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ Exception Telegram : {e}")
        return False


def match_keyword(haystack_norm: str) -> tuple[str | None, str | None]:
    for axe, words in KEYWORDS.items():
        for w in words:
            w_norm = normalize(w)
            # Correspondance mot entier / expression pour éviter les sous-chaînes piégeuses
            pattern = r"(?<![a-z0-9])" + re.escape(w_norm) + r"(?![a-z0-9])"
            if re.search(pattern, haystack_norm):
                return axe, w
    return None, None


def fetch_hespress_articles() -> list[dict]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(URL, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    articles = []
    seen_urls = set()

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href.startswith("https://fr.hespress.com/"):
            continue
        if href in seen_urls or "/category/" in href or "/tag/" in href or href.rstrip("/") == "https://fr.hespress.com":
            continue
        # Les articles Hespress ont généralement un slug avec un identifiant numérique
        if not re.search(r"-\d+\.html$", href):
            continue

        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        if len(title) < 15:
            continue

        parent = a.find_parent(["article", "div", "li"])
        summary = ""
        if parent:
            p = parent.find("p")
            if p:
                summary = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()

        seen_urls.add(href)
        articles.append({
            "titre": title,
            "resume": summary,
            "url": href,
        })

    return articles


def run_realtime() -> None:
    print("🔍 Analyse Hespress en cours (Veille rapide)...")
    history = load_history()
    buffer = load_digest_buffer()

    try:
        articles = fetch_hespress_articles()
    except Exception as e:
        print(f"❌ Erreur lors du scraping Hespress : {e}")
        return

    new_history_urls = []
    alerts_sent = 0
    now_str = morocco_now().strftime("%H:%M")

    for art in articles:
        url = art["url"]
        if url in history:
            continue

        combined_norm = normalize(f"{art['titre']} {art['resume']}")
        axe, kw = match_keyword(combined_norm)
        if not axe:
            continue

        titre_clean = art["titre"][:180]
        resume_clean = (art["resume"][:260] + "...") if len(art["resume"]) > 260 else art["resume"]

        msg = (
            f"🚨 <b>ALERTE HESPRESS [{axe}]</b>\n"
            f"🔑 Mot-clé : <code>{kw}</code> | 🕒 {now_str}\n\n"
            f"📌 <b>{titre_clean}</b>\n"
        )
        if resume_clean:
            msg += f"📝 <i>{resume_clean}</i>\n"
        msg += f"\n🔗 <a href=\"{url}\">Lire l'article complet</a>"

        if send_telegram(msg):
            alerts_sent += 1
            new_history_urls.append(url)
            buffer.append({
                "heure": now_str,
                "axe": axe,
                "mot_cle": kw,
                "titre": titre_clean,
                "resume": resume_clean,
                "url": url,
            })

    if new_history_urls:
        save_history(new_history_urls)
        save_digest_buffer(buffer)

    print(f"✅ Veille terminée : {alerts_sent} nouvelle(s) alerte(s) envoyée(s).")


def build_essay_digest(items: list[dict], date_str: str) -> str:
    grouped = {"DGSN": [], "BUDGET": [], "INTERIEUR": [], "AUTRE": []}
    for it in items:
        axe = it.get("axe", "AUTRE")
        grouped.setdefault(axe, []).append(it)

    lines = [
        f"📝 <b>NOTE DE SYNTHÈSE HESPRESS — {date_str}</b>",
        f"<i>Vue d'ensemble des publications ciblées ({len(items)} article(s) retenu(s)) :</i>\n",
        "Sur la période écoulée, la veille a regroupé les actualités marquantes autour de vos axes prioritaires afin d'en dégager les grandes lignes :",
    ]

    axe_labels = {
        "DGSN": "Sécurité & DGSN",
        "BUDGET": "Budget, PLF & Fiscalité",
        "INTERIEUR": "Administration & Ministère de l'Intérieur",
        "AUTRE": "Autres points suivis",
    }

    for axe, label in axe_labels.items():
        entries = grouped.get(axe, [])
        if not entries:
            continue
        titles_part = " ; ".join(
            f"« {e['titre']} » ({e['heure']}, mot-clé <i>{e['mot_cle']}</i>)"
            for e in entries
        )
        details_part = " ".join(
            e["resume"] for e in entries if e.get("resume")
        )
        paragraph = f"\n<b>{label} :</b> L'attention s'est portée sur {titles_part}."
        if details_part:
            paragraph += f" {details_part}"
        lines.append(paragraph)

    lines.append("\n<b>Sources & liens directs :</b>")
    for idx, it in enumerate(items, start=1):
        lines.append(f"{idx}. [{it.get('axe', '')}] <a href=\"{it['url']}\">{it['titre']}</a>")

    return "\n".join(lines)


def run_digest() -> None:
    print("📝 Génération de la synthèse rédigée...")
    now = morocco_now()
    date_str = now.strftime("%d/%m/%Y")
    buffer = load_digest_buffer()

    if not buffer:
        msg = (
            f"📝 <b>NOTE DE SYNTHÈSE HESPRESS — {date_str}</b>\n\n"
            f"Aucune nouvelle publication ciblée n'a été enregistrée sur ce cycle."
        )
        send_telegram(msg)
        return

    msg = build_essay_digest(buffer, date_str)
    if send_telegram(msg):
        # On vide le tampon uniquement après un envoi réussi
        save_digest_buffer([])
        print("✅ Synthèse envoyée et tampon réinitialisé.")


if __name__ == "__main__":
    mode = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "realtime"
    if mode == "digest":
        run_digest()
    else:
        run_realtime()
