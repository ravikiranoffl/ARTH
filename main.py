import os
import json
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# --- 1. CHRONOLOGICAL SETTINGS (Strict IST Enforcement) ---
IST = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(IST)
current_year = now_ist.strftime("%Y")        
current_date = now_ist.strftime("%Y-%m-%d") 

os.makedirs(current_year, exist_ok=True)
target_filepath = os.path.join(current_year, f"{current_date}.json")

# --- 2. THE ARTH TARGET MATRIX ---
TARGETS = {
    "rbi": {
        "Press Releases": "https://rbi.org.in/pressreleases_rss.xml",
        "Speeches": "https://rbi.org.in/speeches_rss.xml",
        "Notifications": "https://rbi.org.in/notifications_rss.xml",
        "Tenders": "https://rbi.org.in/tenders_rss.xml",
        "Publications": "https://rbi.org.in/Publication_rss.xml"
    },
    "sebi": {
        "Updates": "https://www.sebi.gov.in/sebirss.xml"
    },
    "pib": {
        "Finance": "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&reg=3"
    }
}

def clean_html_text(raw_text):
    """Strips layout structures while preserving massive long-form text blocks."""
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    # Convert paragraph ends and breaks into structural newlines for readability
    text = re.sub(r'(</tr>|</li>|<\/p>|<br\s*\/?>)', '\n', text)
    # Aggressively strip remaining HTML tags
    text = re.compile(r'<[^>]+>').sub('', text)
    # Normalize spacing while keeping intentional line breaks
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

def fetch_payload(url):
    """Fetches raw data bytes securely mirroring standard user-agent environments."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ARTH/Production-Node'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read()
    except Exception as e:
        print(f"[-] Telemetry Node Connection Refused: {url} | Details: {e}")
        return None

def parse_and_normalize(raw_xml, institution):
    """Normalizes formatting variations into standard architectural schemas."""
    normalized_records = []
    if not raw_xml: 
        return normalized_records

    try:
        root = ET.fromstring(raw_xml)
        items = root.findall(".//item") or root.findall(".//entry")
        
        for el in items:
            title_node = el.find("title")
            link_node = el.find("link")
            pub_date_node = el.find("pubDate") or el.find("updated")
            
            # Deep CDATA & Content extraction
            desc_text = ""
            # Some feeds put full articles in content:encoded instead of description
            content_node = el.find("{http://purl.org/rss/1.0/modules/content/}encoded")
            desc_node = el.find("description") or el.find("summary")
            
            if content_node is not None and content_node.text:
                desc_text = content_node.text
            elif desc_node is not None and desc_node.text:
                desc_text = desc_node.text
                
            raw_title = title_node.text.strip() if title_node is not None and title_node.text else "N/A"
            clean_title = html.unescape(raw_title)
            clean_desc = clean_html_text(desc_text)
            
            url = link_node.text.strip() if link_node is not None and link_node.text else "N/A"
            
            if pub_date_node is not None and pub_date_node.text:
                raw_date = pub_date_node.text.strip()
                try:
                    parsed_dt = datetime.strptime(raw_date[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    published_at = parsed_dt.replace(tzinfo=IST).isoformat()
                except Exception:
                    published_at = now_ist.isoformat()
            else:
                published_at = now_ist.isoformat()

            item_id = f"{institution}_{hash(clean_title) & 0xffffffff}"
            
            normalized_records.append({
                "id": item_id,
                "title": clean_title,
                "description": clean_desc,
                "url": url,
                "published_at": published_at
            })
    except Exception as e:
        print(f"[-] Structural anomaly bypassed during processing: {e}")
        
    return normalized_records

def main():
    print(f"[START] Executing ARTH Operational Protocol for coordinate: {current_date}")
    daily_payload = {"rbi": {}, "sebi": {}, "pib": {}}

    if os.path.exists(target_filepath):
        try:
            with open(target_filepath, "r", encoding="utf-8") as f:
                daily_payload = json.load(f)
        except Exception:
            print("[WARN] Target path signature dirty. Re-allocating file block.")

    for institution, categories in TARGETS.items():
        if institution not in daily_payload:
            daily_payload[institution] = {}
            
        for category_name, link_url in categories.items():
            print(f"[EXT] Syncing Node -> {institution.upper()} [{category_name}]")
            
            xml_bytes = fetch_payload(link_url)
            dataset = parse_and_normalize(xml_bytes, institution)
            
            if category_name not in daily_payload[institution]:
                daily_payload[institution][category_name] = []
                
            existing_list = daily_payload[institution][category_name]
            existing_signatures = {record["id"] for record in existing_list}
            
            new_entries = []
            novel_write_count = 0
            
            for entry in dataset:
                if entry["id"] not in existing_signatures:
                    new_entries.append(entry)
                    novel_write_count += 1
            
            # FORCE NEW ENTRIES TO THE TOP OF THE JSON ARRAY
            if new_entries:
                daily_payload[institution][category_name] = new_entries + existing_list
            
            print(f"      Log: Storage committed with +{novel_write_count} novel entries prepended to top.")

    try:
        with open(target_filepath, "w", encoding="utf-8") as f:
            json.dump(daily_payload, f, ensure_ascii=False, indent=4)
        print(f"[SUCCESS] Core synchronization verified. Matrix secure at: {target_filepath}")
    except Exception as e:
        print(f"[-] CRITICAL WRITE BLOCKED: {e}")

if __name__ == "__main__":
    main()
