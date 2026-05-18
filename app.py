
import json
import html
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title="RuokaVirta HexMap", layout="wide")

TYPE_COLORS = {
    "Havainto": "#fff3bf",
    "Este": "#ffc9c9",
    "Mahdollisuus": "#d3f9d8",
    "Toimija": "#d0ebff",
    "Tieto": "#e5dbff",
    "Kokeilu": "#ffd8a8",
    "Muuttuja": "#c3fae8",
}

SIDES = {
    "Oikea": (1, 0, 0),
    "Yläoikea": (0, -1, -60),
    "Ylävasen": (-1, -1, -120),
    "Vasen": (-1, 0, 180),
    "Alavasen": (0, 1, 120),
    "Alaoikea": (1, 1, 60),
}

REL_TYPES = [
    "vaikuttaa",
    "mahdollistaa",
    "estää",
    "riippuu",
    "aiheuttaa",
    "vahvistaa",
    "heikentää",
    "muu yhteys",
]

def init_state():
    if "cards" not in st.session_state:
        st.session_state.cards = []
    if "links" not in st.session_state:
        st.session_state.links = []
    if "next_id" not in st.session_state:
        st.session_state.next_id = 1
    if "message" not in st.session_state:
        st.session_state.message = ""

init_state()

def get_card(card_id):
    return next((c for c in st.session_state.cards if c["id"] == card_id), None)

def occupied_positions(exclude_id=None):
    pos = {}
    for c in st.session_state.cards:
        if exclude_id is not None and c["id"] == exclude_id:
            continue
        if c.get("placed"):
            pos[(c.get("q", 0), c.get("r", 0))] = c["id"]
    return pos

def add_card(title, card_type, theme, actor, description):
    card_id = st.session_state.next_id
    st.session_state.next_id += 1

    placed = len([c for c in st.session_state.cards if c.get("placed")]) == 0
    card = {
        "id": card_id,
        "title": title.strip() or f"Uusi kortti {card_id}",
        "type": card_type,
        "theme": theme.strip(),
        "actor": actor.strip(),
        "description": description.strip(),
        "cluster": "",
        "variable": "",
        "metric": "",
        "data_source": "",
        "experiment": "",
        "placed": placed,
        "q": 0 if placed else None,
        "r": 0 if placed else None,
        "rotation": 0,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    st.session_state.cards.append(card)
    st.session_state.message = f"Lisätty kortti #{card_id}: {card['title']}"

def add_examples():
    if st.session_state.cards:
        st.session_state.message = "Esimerkkejä ei lisätty, koska kortteja on jo olemassa."
        return
    examples = [
        ("Pienet toimituserät nostavat kustannuksia", "Este", "Kuljetus", "Tuottaja / kuljettaja", "Vajaakuormat ja noutojen hajanaisuus nostavat yksikkökustannusta."),
        ("Ravintolat eivät tiedä saatavuutta ajoissa", "Este", "Data", "Ravintola", "Saatavuustiedon puute vaikeuttaa ruokalistasuunnittelua."),
        ("Yhteinen tilausikkuna", "Mahdollisuus", "Koordinointi", "Tuottajat ja ravintolat", "Tilaukset kerätään tiettyyn aikaan, jolloin kuljetuksia voidaan yhdistää."),
        ("Kylmäketjun vaatimukset", "Este", "Kylmäketju", "Kuljettaja", "Eri tuotteet tarvitsevat eri lämpötiloja."),
        ("Täyttöaste", "Muuttuja", "Mittari", "Kuljettaja", "Kuljetuskapasiteetin käyttöaste."),
        ("Noutopiste tai mikroterminaali", "Kokeilu", "Jakelu", "Kaikki toimijat", "Yksi paikka, johon tuotteita voidaan keskittää."),
    ]
    for e in examples:
        add_card(*e)
    # Place examples into a small connected shape
    coords = [(0,0), (1,0), (0,-1), (-1,-1), (-1,0), (0,1)]
    for c, (q, r) in zip(st.session_state.cards, coords):
        c["placed"] = True
        c["q"] = q
        c["r"] = r
    st.session_state.message = "Esimerkkikortit lisätty."

def connect_cards(source_id, target_id, side, rel_type, explanation, force_move=False):
    if source_id == target_id:
        st.session_state.message = "Lähtö- ja kohdekortti eivät voi olla sama kortti."
        return

    source = get_card(source_id)
    target = get_card(target_id)
    if not source or not target:
        st.session_state.message = "Korttia ei löytynyt."
        return

    if not source.get("placed"):
        source["placed"] = True
        source["q"] = 0
        source["r"] = 0
        source["rotation"] = 0

    dq, dr, rot = SIDES[side]
    new_q = source["q"] + dq
    new_r = source["r"] + dr

    occ = occupied_positions(exclude_id=target_id if force_move else None)
    if (new_q, new_r) in occ:
        st.session_state.message = f"Paikka on jo käytössä kortilla #{occ[(new_q, new_r)]}. Valitse toinen sivu."
        return

    if target.get("placed") and not force_move:
        st.session_state.message = "Kohdekortti on jo kartalla. Valitse 'Siirrä kohdekortti uuteen paikkaan', jos haluat siirtää sen."
        return

    target["placed"] = True
    target["q"] = new_q
    target["r"] = new_r
    target["rotation"] = rot

    st.session_state.links.append({
        "from_card_id": source_id,
        "to_card_id": target_id,
        "side": side,
        "relationship_type": rel_type,
        "explanation": explanation.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    st.session_state.message = f"Kytketty #{target_id} kortin #{source_id} sivuun: {side}."

def hex_to_pixel(q, r, size=86):
    # Pointy-top axial coordinates.
    # x/y values are tuned for CSS hexagons that are 150 x 130 px.
    x = size * 1.52 * q
    y = size * 1.32 * (r + q / 2)
    return x, y

def map_bounds(cards, size=86):
    placed = [c for c in cards if c.get("placed")]
    if not placed:
        return 0, 0, 700, 360
    pts = [hex_to_pixel(c["q"], c["r"], size) for c in placed]
    min_x = min(x for x, y in pts) - 120
    max_x = max(x for x, y in pts) + 260
    min_y = min(y for x, y in pts) - 110
    max_y = max(y for x, y in pts) + 220
    return min_x, min_y, max_x - min_x, max_y - min_y

def card_div(card, min_x, min_y, size=86):
    x, y = hex_to_pixel(card["q"], card["r"], size)
    left = x - min_x
    top = y - min_y
    bg = TYPE_COLORS.get(card["type"], "#f1f3f5")
    title = html.escape(card.get("title", ""))
    meta_parts = [card.get("type", ""), card.get("theme", "")]
    meta = html.escape(" · ".join([p for p in meta_parts if p]))
    rot = int(card.get("rotation", 0))
    return (
        f'<div class="hex-wrap" style="left:{left}px; top:{top}px; --rot:{rot}deg;">'
        f'<div class="hex" style="background:{bg};">'
        f'<div class="hex-inner">'
        f'<div class="hex-id">#{card["id"]}</div>'
        f'<div class="hex-title">{title}</div>'
        f'<div class="hex-meta">{meta}</div>'
        f'</div></div></div>'
    )

def line_svg(link, min_x, min_y, size=86):
    a = get_card(link["from_card_id"])
    b = get_card(link["to_card_id"])
    if not a or not b or not a.get("placed") or not b.get("placed"):
        return ""
    ax, ay = hex_to_pixel(a["q"], a["r"], size)
    bx, by = hex_to_pixel(b["q"], b["r"], size)
    # centers of visual hexagons
    x1 = ax - min_x + 75
    y1 = ay - min_y + 65
    x2 = bx - min_x + 75
    y2 = by - min_y + 65
    label = html.escape(link.get("relationship_type", ""))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="link-line" />'
        f'<text x="{mx}" y="{my - 5}" class="link-label">{label}</text>'
    )

def render_map():
    placed = [c for c in st.session_state.cards if c.get("placed")]
    if not placed:
        st.info("Kartalla ei ole vielä sijoitettuja kortteja. Ensimmäinen lisätty kortti sijoitetaan keskelle.")
        return

    min_x, min_y, width, height = map_bounds(st.session_state.cards)
    width = max(700, int(width))
    height = max(360, int(height))

    svg_lines = "".join(line_svg(l, min_x, min_y) for l in st.session_state.links)
    cards_html = "".join(card_div(c, min_x, min_y) for c in placed)

    html_block = (
        f'<div class="hex-map" style="width:{width}px;height:{height}px;">'
        f'<svg class="link-layer" width="{width}" height="{height}">{svg_lines}</svg>'
        f'{cards_html}'
        f'</div>'
    )
    st.markdown(html_block, unsafe_allow_html=True)

def export_json():
    return json.dumps(
        {"cards": st.session_state.cards, "links": st.session_state.links},
        ensure_ascii=False,
        indent=2,
    )

def export_excel_bytes():
    output = BytesIO()
    cards_df = pd.DataFrame(st.session_state.cards)
    links_df = pd.DataFrame(st.session_state.links)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        cards_df.to_excel(writer, index=False, sheet_name="cards")
        links_df.to_excel(writer, index=False, sheet_name="links")
    output.seek(0)
    return output.getvalue()

st.markdown(
    """
<style>
.block-container { padding-top: 2rem; max-width: 1500px; }
.small-note { color:#6c757d; font-size:0.92rem; margin-bottom:1.5rem; }
.hex-map-outer {
    width: 100%;
    overflow: auto;
    border: 1px solid #dee2e6;
    border-radius: 14px;
    background:
        radial-gradient(circle at 1px 1px, rgba(0,0,0,.06) 1px, transparent 0);
    background-size: 26px 26px;
    padding: 16px;
}
.hex-map {
    position: relative;
    margin: 0;
    background: transparent;
}
.link-layer {
    position:absolute;
    left:0;
    top:0;
    z-index:1;
    pointer-events:none;
}
.link-line {
    stroke:#868e96;
    stroke-width:2;
    stroke-dasharray:5 5;
}
.link-label {
    font-size:11px;
    fill:#495057;
    paint-order: stroke;
    stroke:#ffffff;
    stroke-width:3px;
    stroke-linejoin:round;
}
.hex-wrap {
    position:absolute;
    width:150px;
    height:130px;
    z-index:2;
    transform: rotate(var(--rot));
    transform-origin: 75px 65px;
}
.hex {
    width:150px;
    height:130px;
    clip-path: polygon(25% 4%, 75% 4%, 100% 50%, 75% 96%, 25% 96%, 0% 50%);
    display:flex;
    align-items:center;
    justify-content:center;
    box-shadow: 0 1px 2px rgba(0,0,0,.08);
}
.hex-inner {
    width:112px;
    text-align:center;
    transform: rotate(calc(-1 * var(--rot)));
    transform-origin:center center;
    font-family: system-ui, -apple-system, Segoe UI, sans-serif;
}
.hex-id {
    font-size:10px;
    color:#868e96;
    margin-bottom:5px;
}
.hex-title {
    font-weight:700;
    color:#212529;
    font-size:13px;
    line-height:1.15;
    overflow-wrap:anywhere;
}
.hex-meta {
    margin-top:7px;
    color:#6c757d;
    font-size:10px;
    line-height:1.15;
    overflow-wrap:anywhere;
}
.unplaced {
    border:1px dashed #adb5bd;
    border-radius:12px;
    padding:10px;
    margin:6px 0;
    background:#f8f9fa;
}
@media (max-width: 800px) {
    .hex-map-outer { max-height: 520px; }
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("RuokaVirta HexMap")
st.markdown('<div class="small-note">Sivukytkentäinen kuusikulmakartta ruokalogistiikan havaintojen, yhteyksien, muuttujien ja kokeilujen keräämiseen.</div>', unsafe_allow_html=True)

if st.session_state.message:
    st.success(st.session_state.message)

left, right = st.columns([0.95, 1.55], gap="large")

with left:
    st.subheader("Lisää kortti")
    with st.form("add_card_form", clear_on_submit=True):
        title = st.text_input("Kortin otsikko")
        card_type = st.selectbox("Korttityyppi", list(TYPE_COLORS.keys()))
        theme = st.text_input("Teema", placeholder="esim. kuljetus, data, kylmäketju")
        actor = st.text_input("Toimija", placeholder="esim. tuottaja, ravintola, kuljettaja")
        description = st.text_area("Lisäkuvaus")
        submitted = st.form_submit_button("Lisää kortti")
        if submitted:
            add_card(title, card_type, theme, actor, description)
            st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Lisää esimerkit"):
            add_examples()
            st.rerun()
    with c2:
        if st.button("Tyhjennä kaikki"):
            st.session_state.cards = []
            st.session_state.links = []
            st.session_state.next_id = 1
            st.session_state.message = "Kartta tyhjennetty."
            st.rerun()

    st.divider()
    st.subheader("Sijoittamattomat kortit")
    unplaced = [c for c in st.session_state.cards if not c.get("placed")]
    if not unplaced:
        st.caption("Ei sijoittamattomia kortteja.")
    else:
        for c in unplaced:
            st.markdown(f'<div class="unplaced"><b>#{c["id"]} {html.escape(c["title"])}</b><br><small>{html.escape(c["type"])} · {html.escape(c.get("theme",""))}</small></div>', unsafe_allow_html=True)

with right:
    st.subheader("Korttitila")
    st.markdown('<div class="hex-map-outer">', unsafe_allow_html=True)
    render_map()
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Kytke kortti sivuun")

    if len(st.session_state.cards) < 2:
        st.caption("Lisää vähintään kaksi korttia, jotta voit tehdä yhteyden.")
    else:
        placed_cards = [c for c in st.session_state.cards if c.get("placed")]
        all_cards = st.session_state.cards
        source_options = {f'#{c["id"]} {c["title"]}': c["id"] for c in placed_cards or all_cards}
        target_options = {f'#{c["id"]} {c["title"]}': c["id"] for c in all_cards}

        with st.form("connect_form"):
            source_label = st.selectbox("Lähtökortti kartalla", list(source_options.keys()))
            side = st.selectbox("Mihin sivuun kohdekortti asetetaan?", list(SIDES.keys()))
            target_label = st.selectbox("Kohdekortti", list(target_options.keys()))
            rel_type = st.selectbox("Yhteyden tyyppi", REL_TYPES)
            explanation = st.text_area("Miksi nämä liittyvät toisiinsa?", placeholder="Kirjoita lyhyt perustelu yhteydelle.")
            force_move = st.checkbox("Siirrä kohdekortti uuteen paikkaan, vaikka se olisi jo kartalla")
            submitted = st.form_submit_button("Kytke kortit")
            if submitted:
                connect_cards(
                    source_options[source_label],
                    target_options[target_label],
                    side,
                    rel_type,
                    explanation,
                    force_move=force_move,
                )
                st.rerun()

    st.divider()
    st.subheader("Korttien tarkennukset")

    if st.session_state.cards:
        options = {f'#{c["id"]} {c["title"]}': c["id"] for c in st.session_state.cards}
        selected_label = st.selectbox("Valitse muokattava kortti", list(options.keys()))
        card = get_card(options[selected_label])
        with st.form("details_form"):
            cluster = st.text_input("Klusteri", value=card.get("cluster", ""))
            variable = st.text_input("Muuttujaehdotus", value=card.get("variable", ""), placeholder="esim. täyttöaste, toimituserän koko")
            metric = st.text_input("Mittari", value=card.get("metric", ""))
            data_source = st.text_input("Mahdollinen datalähde", value=card.get("data_source", ""))
            experiment = st.text_area("Kokeiluidea", value=card.get("experiment", ""))
            if st.form_submit_button("Tallenna tarkennukset"):
                card["cluster"] = cluster.strip()
                card["variable"] = variable.strip()
                card["metric"] = metric.strip()
                card["data_source"] = data_source.strip()
                card["experiment"] = experiment.strip()
                st.session_state.message = f"Tarkennukset tallennettu kortille #{card['id']}."
                st.rerun()
    else:
        st.caption("Ei kortteja vielä.")

    st.divider()
    st.subheader("Vienti ja tuonti")

    st.download_button(
        "Lataa JSON",
        data=export_json(),
        file_name="ruokavirta_hexmap.json",
        mime="application/json",
    )

    if st.session_state.cards:
        st.download_button(
            "Lataa Excel",
            data=export_excel_bytes(),
            file_name="ruokavirta_hexmap.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    uploaded = st.file_uploader("Tuo JSON", type=["json"])
    if uploaded is not None:
        try:
            data = json.load(uploaded)
            st.session_state.cards = data.get("cards", [])
            st.session_state.links = data.get("links", [])
            if st.session_state.cards:
                st.session_state.next_id = max(c["id"] for c in st.session_state.cards) + 1
            else:
                st.session_state.next_id = 1
            st.session_state.message = "JSON tuotu onnistuneesti."
            st.rerun()
        except Exception as e:
            st.error(f"JSON-tuonti epäonnistui: {e}")
