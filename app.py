import json
import html
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title="RuokaVirta HexMap", layout="wide")

CARD_TYPES = ["Havainto", "Este", "Mahdollisuus", "Toimija", "Tieto", "Kokeilu", "Muuttuja"]
REL_TYPES = ["liittyy", "vaikuttaa", "estää", "mahdollistaa", "aiheuttaa", "riippuu", "vahvistaa", "heikentää"]

TYPE_COLORS = {
    "Havainto": "#fff3bf",
    "Este": "#ffc9c9",
    "Mahdollisuus": "#d3f9d8",
    "Toimija": "#d0ebff",
    "Tieto": "#e5dbff",
    "Kokeilu": "#ffe8cc",
    "Muuttuja": "#c5f6fa",
}


def init_state():
    st.session_state.setdefault("cards", [])
    st.session_state.setdefault("links", [])
    st.session_state.setdefault("next_id", 1)


def add_card(title, card_type, theme, actor, description):
    title = (title or "").strip() or f"Uusi kortti {st.session_state.next_id}"
    card = {
        "id": st.session_state.next_id,
        "title": title,
        "type": card_type,
        "theme": theme.strip(),
        "actor": actor.strip(),
        "description": description.strip(),
        "cluster": "",
        "variable": "",
        "metric": "",
        "data_source": "",
        "experiment": "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    st.session_state.cards.append(card)
    st.session_state.next_id += 1


def add_examples():
    examples = [
        ("Pienet toimituserät nostavat kustannuksia", "Este", "Kuljetus", "Tuottaja / kuljetus"),
        ("Autot ajavat vajaana", "Havainto", "Kuljetus", "Kuljetusyrittäjä"),
        ("Ravintola ei tiedä saatavuutta ajoissa", "Tieto", "Kysyntä", "Ravintola"),
        ("Yhteinen tilausikkuna voisi auttaa", "Kokeilu", "Koordinointi", "Ravintolat / tuottajat"),
        ("Kylmäketju rajoittaa yhteiskuljetuksia", "Este", "Kylmäketju", "Kuljetus"),
        ("Sesonkivaihtelu lisää hävikkiriskiä", "Havainto", "Tarjonta", "Tuottaja"),
        ("Saatavuustiedon ajantasaisuus", "Muuttuja", "Data", "Kaikki"),
    ]
    for title, typ, theme, actor in examples:
        add_card(title, typ, theme, actor, "")


def export_json():
    data = {
        "cards": st.session_state.cards,
        "links": st.session_state.links,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def export_excel():
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(st.session_state.cards).to_excel(writer, sheet_name="cards", index=False)
        pd.DataFrame(st.session_state.links).to_excel(writer, sheet_name="links", index=False)
    output.seek(0)
    return output


def card_html(card):
    bg = TYPE_COLORS.get(card["type"], "#f1f3f5")
    title = html.escape(card.get("title", ""))
    meta = html.escape(f'{card.get("type", "")} · {card.get("theme", "")}'.strip(" ·"))
    # Tärkeää: palautetaan HTML ilman rivinvaihtoja ja sisennyksiä.
    # Muuten Streamlit/Markdown voi tulkita osan kortista koodilohkoksi.
    return (
        f'<div class="hex" style="background:{bg};">'
        f'<div class="hex-inner">'
        f'<div class="hex-id">#{card["id"]}</div>'
        f'<div class="hex-title">{title}</div>'
        f'<div class="hex-meta">{meta}</div>'
        f'</div></div>'
    )


init_state()

st.title("RuokaVirta HexMap")
st.caption("Kevyt työpajasovellus ruokalogistiikan havaintojen, yhteyksien, muuttujien ja kokeilujen keräämiseen.")

st.markdown(
    """
<style>
.hex-grid { display:flex; flex-wrap:wrap; gap:18px; align-items:center; margin-top: 1rem; }
.hex { width: 170px; height: 148px; clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%); display:flex; align-items:center; justify-content:center; padding: 12px; box-sizing:border-box; border:1px solid rgba(0,0,0,.15); }
.hex-inner { text-align:center; max-width:135px; }
.hex-id { font-size:11px; opacity:.65; }
.hex-title { font-weight:700; font-size:14px; line-height:1.15; margin:6px 0; }
.hex-meta { font-size:11px; opacity:.75; }
.link-card { border:1px solid #ddd; border-radius:10px; padding:10px; margin-bottom:8px; background:#fff; }
</style>
""",
    unsafe_allow_html=True,
)

left, right = st.columns([1, 2])

with left:
    st.subheader("Lisää kortti")
    with st.form("add_card_form", clear_on_submit=True):
        title = st.text_input("Kortin otsikko")
        card_type = st.selectbox("Korttityyppi", CARD_TYPES)
        theme = st.text_input("Teema", placeholder="esim. kuljetus, data, kylmäketju")
        actor = st.text_input("Toimija", placeholder="esim. tuottaja, ravintola, kuljettaja")
        description = st.text_area("Lisäkuvaus", height=90)
        submitted = st.form_submit_button("Lisää kortti")
        if submitted:
            add_card(title, card_type, theme, actor, description)
            st.success("Kortti lisätty.")

    col_a, col_b = st.columns(2)
    if col_a.button("Lisää esimerkit"):
        add_examples()
        st.success("Esimerkkikortit lisätty.")
    if col_b.button("Tyhjennä kaikki"):
        st.session_state.cards = []
        st.session_state.links = []
        st.session_state.next_id = 1
        st.success("Tyhjennetty.")

    st.divider()
    st.subheader("Yhdistä kortteja")
    if len(st.session_state.cards) >= 2:
        card_options = {f"#{c['id']} {c['title']}": c["id"] for c in st.session_state.cards}
        with st.form("add_link_form", clear_on_submit=True):
            from_label = st.selectbox("Kortti A", list(card_options.keys()), key="from_card")
            to_label = st.selectbox("Kortti B", list(card_options.keys()), key="to_card")
            rel_type = st.selectbox("Yhteyden tyyppi", REL_TYPES)
            strength = st.slider("Yhteyden vahvuus", 1, 5, 3)
            explanation = st.text_area("Miksi nämä liittyvät toisiinsa?", height=90)
            link_submitted = st.form_submit_button("Lisää yhteys")
            if link_submitted:
                from_id = card_options[from_label]
                to_id = card_options[to_label]
                if from_id == to_id:
                    st.warning("Valitse kaksi eri korttia.")
                else:
                    st.session_state.links.append({
                        "from_card_id": from_id,
                        "to_card_id": to_id,
                        "relationship_type": rel_type,
                        "strength": strength,
                        "explanation": explanation.strip(),
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    })
                    st.success("Yhteys lisätty.")
    else:
        st.info("Lisää vähintään kaksi korttia, niin voit luoda yhteyksiä.")

    st.divider()
    st.subheader("Vie aineisto")
    st.download_button("Lataa JSON", data=export_json(), file_name="ruokavirta_hexmap.json", mime="application/json")
    st.download_button("Lataa Excel", data=export_excel(), file_name="ruokavirta_hexmap.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with right:
    st.subheader("Korttitila")
    if not st.session_state.cards:
        st.info("Kortteja ei vielä ole. Lisää kortti tai paina 'Lisää esimerkit'.")
    else:
        cards_html = '<div class="hex-grid">' + "".join(card_html(c) for c in st.session_state.cards) + "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)

    st.divider()
    st.subheader("Korttien tarkennukset")
    if st.session_state.cards:
        selected = st.selectbox("Valitse muokattava kortti", [f"#{c['id']} {c['title']}" for c in st.session_state.cards])
        selected_id = int(selected.split(" ")[0].replace("#", ""))
        card = next(c for c in st.session_state.cards if c["id"] == selected_id)
        with st.form("edit_card_form"):
            cluster = st.text_input("Klusteri", value=card.get("cluster", ""))
            variable = st.text_input("Muuttujaehdotus", value=card.get("variable", ""), placeholder="esim. täyttöaste, toimituserän koko")
            metric = st.text_input("Mahdollinen mittari", value=card.get("metric", ""), placeholder="esim. kg/toimitus, €/kg, tuntia/viikko")
            data_source = st.text_input("Mahdollinen datalähde", value=card.get("data_source", ""))
            experiment = st.text_area("Kokeiluidea", value=card.get("experiment", ""), height=90)
            save = st.form_submit_button("Tallenna tarkennukset")
            if save:
                card["cluster"] = cluster.strip()
                card["variable"] = variable.strip()
                card["metric"] = metric.strip()
                card["data_source"] = data_source.strip()
                card["experiment"] = experiment.strip()
                st.success("Tarkennukset tallennettu.")

    st.divider()
    st.subheader("Yhteydet")
    if not st.session_state.links:
        st.caption("Ei yhteyksiä vielä.")
    else:
        id_to_title = {c["id"]: c["title"] for c in st.session_state.cards}
        for i, link in enumerate(st.session_state.links, start=1):
            st.markdown(
                f"""
<div class="link-card">
<b>{i}. #{link['from_card_id']} {id_to_title.get(link['from_card_id'], '')}</b><br>
→ <b>#{link['to_card_id']} {id_to_title.get(link['to_card_id'], '')}</b><br>
Tyyppi: {link['relationship_type']} · Vahvuus: {link['strength']}<br>
<i>{link.get('explanation','')}</i>
</div>
""",
                unsafe_allow_html=True,
            )
