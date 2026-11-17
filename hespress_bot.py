import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

URL = "https://fr.hespress.com/"
HISTORY_FILE = "historique_hespress.txt"
DIGEST_FILE = "articles_du_jour.json"

TELEGRAM_TOKEN = os.environ.get("HESPRESS_TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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
        print("Variables HESPRESS_TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID manquantes.")
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
            print(f"Erreur Telegram ({r.status_code}) : {r.text}")
            return False
        return True
    except Exception as e:
        print(f"Exception Telegram : {e}")
        return False


def match_keyword(haystack_norm: str) -> tuple[str | None, str | None]:
    for axe, words in KEYWORDS.items():
        for w in words:
            w_norm = normalize(w)
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
        raw_href = (a.get("href") or "").strip()
        if not raw_href or raw_href.startswith("#") or raw_href.startswith("mailto:") or raw_href.startswith("javascript:"):
            continue

        href = urljoin(URL, raw_href)
        if not href.startswith("https://fr.hespress.com/"):
            continue

        clean_href = href.split("?")[0].rstrip("/")
        if (
            clean_href in seen_urls
            or clean_href == "https://fr.hespress.com"
            or "/category/" in clean_href
            or "/tag/" in clean_href
            or "/author/" in clean_href
        ):
            continue

        if not re.search(r"-\d+(\.html)?$", clean_href) and not re.search(r"/\d{4}/\d{2}/", clean_href):
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

        seen_urls.add(clean_href)
        articles.append({
            "titre": title,
            "resume": summary,
            "url": clean_href,
        })

    return articles


def run_realtime() -> None:
    print("Analyse Hespress en cours...")
    history = load_history()
    buffer = load_digest_buffer()

    try:
        articles = fetch_hespress_articles()
    except Exception as e:
        print(f"Erreur scraping Hespress : {e}")
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
        resume_clean = (art["resume"][:240] + "...") if len(art["resume"]) > 240 else art["resume"]

        msg = (
            f"<b>[{axe}]</b> ({kw} — {now_str})\n"
            f"<b>{titre_clean}</b>\n"
        )
        if resume_clean:
            msg += f"{resume_clean}\n"
        msg += f"<a href=\"{url}\">{url}</a>"

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

    print(f"Terminé : {alerts_sent} nouvelle(s) alerte(s) envoyée(s).")


def build_simple_digest(items: list[dict], date_str: str) -> str:
    lines = [
        f"<b>Résumé Hespress — {date_str}</b>",
        f"Total : {len(items)} article(s)\n",
    ]
    for idx, it in enumerate(items, start=1):
        axe = it.get("axe", "AUTRE")
        heure = it.get("heure", "")
        titre = it.get("titre", "")
        url = it.get("url", "")
        lines.append(f"{idx}. <b>[{axe}]</b> {titre} ({heure})")
        if url:
            lines.append(f"   <a href=\"{url}\">{url}</a>")
    return "\n".join(lines)


def run_digest() -> None:
    now = morocco_now()
    date_str = now.strftime("%d/%m/%Y")
    buffer = load_digest_buffer()

    if not buffer:
        send_telegram(f"<b>Résumé Hespress — {date_str}</b>\nAucun nouvel article.")
        return

    msg = build_simple_digest(buffer, date_str)
    if send_telegram(msg):
        save_digest_buffer([])


if __name__ == "__main__":
    mode = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "realtime"
    if mode == "digest":
        run_digest()
    else:
        run_realtime()
