
import json
import html
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title="RuokaVirta HexMap", layout="wide")

# --- Basic settings ---------------------------------------------------------

TYPE_COLORS = {
    "Havainto": "#fff3bf",
    "Este": "#ffc9c9",
    "Mahdollisuus": "#d3f9d8",
    "Toimija": "#d0ebff",
    "Tieto": "#e5dbff",
    "Kokeilu": "#ffd8a8",
}

SIDES = {
    "→ oikealle": (1, 0, 0),
    "↗ yläoikealle": (0, -1, -60),
    "↖ ylävasemmalle": (-1, -1, -120),
    "← vasemmalle": (-1, 0, 180),
    "↙ alavasemmalle": (0, 1, 120),
    "↘ alaoikealle": (1, 1, 60),
}

REL_TYPES = ["liittyy", "mahdollistaa", "estää", "vahvistaa", "heikentää"]

# --- Session state ---------------------------------------------------------

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

# --- Data functions --------------------------------------------------------

def get_card(card_id):
    return next((c for c in st.session_state.cards if c["id"] == card_id), None)

def occupied_positions(exclude_id=None):
    positions = {}
    for c in st.session_state.cards:
        if exclude_id is not None and c["id"] == exclude_id:
            continue
        if c.get("placed"):
            positions[(c.get("q", 0), c.get("r", 0))] = c["id"]
    return positions

def add_card(title, card_type="Havainto", note=""):
    card_id = st.session_state.next_id
    st.session_state.next_id += 1

    is_first = len([c for c in st.session_state.cards if c.get("placed")]) == 0

    st.session_state.cards.append({
        "id": card_id,
        "title": title.strip() or f"Kortti {card_id}",
        "type": card_type,
        "note": note.strip(),
        "placed": is_first,
        "q": 0 if is_first else None,
        "r": 0 if is_first else None,
        "rotation": 0,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    st.session_state.message = f"Lisätty kortti #{card_id}"

def add_examples():
    if st.session_state.cards:
        st.session_state.message = "Tyhjennä kartta ennen esimerkkien lisäämistä."
        return

    examples = [
        ("Pienet toimituserät", "Este"),
        ("Korkea kuljetuskustannus", "Este"),
        ("Yhteinen tilausikkuna", "Mahdollisuus"),
        ("Saatavuustieto", "Tieto"),
        ("Ravintolan tilauspäätös", "Havainto"),
        ("Noutopiste", "Kokeilu"),
    ]

    for title, card_type in examples:
        add_card(title, card_type)

    coords = [(0, 0), (1, 0), (0, -1), (-1, -1), (-1, 0), (0, 1)]
    rotations = [0, 0, -60, -120, 180, 120]
    for c, (q, r), rot in zip(st.session_state.cards, coords, rotations):
        c["placed"] = True
        c["q"] = q
        c["r"] = r
        c["rotation"] = rot

    st.session_state.links = [
        {"from_card_id": 1, "to_card_id": 2, "side": "→ oikealle", "relationship_type": "vahvistaa", "explanation": ""},
        {"from_card_id": 1, "to_card_id": 3, "side": "↗ yläoikealle", "relationship_type": "mahdollistaa", "explanation": ""},
        {"from_card_id": 4, "to_card_id": 5, "side": "→ oikealle", "relationship_type": "liittyy", "explanation": ""},
    ]
    st.session_state.message = "Esimerkkikartta lisätty."

def connect_cards(source_id, target_id, side, rel_type="liittyy", explanation="", force_move=False):
    if source_id == target_id:
        st.session_state.message = "Valitse kaksi eri korttia."
        return

    source = get_card(source_id)
    target = get_card(target_id)

    if source is None or target is None:
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

    occupied = occupied_positions(exclude_id=target_id if force_move else None)

    if (new_q, new_r) in occupied:
        st.session_state.message = f"Tällä sivulla on jo kortti #{occupied[(new_q, new_r)]}. Valitse toinen sivu."
        return

    if target.get("placed") and not force_move:
        st.session_state.message = "Kohdekortti on jo kartalla. Valitse siirto vain, jos haluat siirtää sen uuteen kohtaan."
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

    st.session_state.message = f"Kytketty #{target_id} kortin #{source_id} sivuun."

# --- Drawing functions -----------------------------------------------------

def hex_to_pixel(q, r, size=88):
    # Axial coordinates, pointy-top visual hexagons.
    x = size * 1.52 * q
    y = size * 1.32 * (r + q / 2)
    return x, y

def map_bounds(cards, size=88):
    placed = [c for c in cards if c.get("placed")]
    if not placed:
        return 0, 0, 760, 440

    points = [hex_to_pixel(c["q"], c["r"], size) for c in placed]
    min_x = min(x for x, _ in points) - 130
    max_x = max(x for x, _ in points) + 280
    min_y = min(y for _, y in points) - 120
    max_y = max(y for _, y in points) + 230

    return min_x, min_y, max(760, int(max_x - min_x)), max(440, int(max_y - min_y))

def card_html(card, min_x, min_y, size=88):
    x, y = hex_to_pixel(card["q"], card["r"], size)
    left = x - min_x
    top = y - min_y
    bg = TYPE_COLORS.get(card.get("type", "Havainto"), "#f1f3f5")
    title = html.escape(card.get("title", ""))
    rot = int(card.get("rotation", 0))

    # Outer hex rotates; inner text counter-rotates, so text stays horizontal.
    return (
        f'<div class="hex-wrap" style="left:{left}px; top:{top}px; --rot:{rot}deg;">'
        f'<div class="hex" style="background:{bg};">'
        f'<div class="hex-inner">'
        f'<div class="hex-id">#{card["id"]}</div>'
        f'<div class="hex-title">{title}</div>'
        f'</div></div></div>'
    )

def link_svg(link, min_x, min_y, size=88):
    a = get_card(link["from_card_id"])
    b = get_card(link["to_card_id"])
    if not a or not b or not a.get("placed") or not b.get("placed"):
        return ""

    ax, ay = hex_to_pixel(a["q"], a["r"], size)
    bx, by = hex_to_pixel(b["q"], b["r"], size)

    x1 = ax - min_x + 78
    y1 = ay - min_y + 68
    x2 = bx - min_x + 78
    y2 = by - min_y + 68

    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="link-line" />'

def render_map():
    placed = [c for c in st.session_state.cards if c.get("placed")]

    if not placed:
        inner = '<div class="empty-map">Lisää ensimmäinen kortti. Se tulee kartan keskelle.</div>'
        st.markdown(f'<div class="hex-map-outer">{inner}</div>', unsafe_allow_html=True)
        return

    min_x, min_y, width, height = map_bounds(st.session_state.cards)
    lines = "".join(link_svg(l, min_x, min_y) for l in st.session_state.links)
    cards = "".join(card_html(c, min_x, min_y) for c in placed)

    html_block = (
        f'<div class="hex-map-outer">'
        f'<div class="hex-map" style="width:{width}px;height:{height}px;">'
        f'<svg class="link-layer" width="{width}" height="{height}">{lines}</svg>'
        f'{cards}'
        f'</div>'
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
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(st.session_state.cards).to_excel(writer, index=False, sheet_name="cards")
        pd.DataFrame(st.session_state.links).to_excel(writer, index=False, sheet_name="links")
    output.seek(0)
    return output.getvalue()

# --- CSS -------------------------------------------------------------------

st.markdown(
    """
<style>
.block-container { padding-top: 1.5rem; max-width: 1500px; }
h1 { margin-bottom: 0.2rem; }
.subtitle { color:#6c757d; margin-bottom: 1.2rem; }
.section-card {
    border:1px solid #dee2e6;
    border-radius:14px;
    padding:16px;
    background:white;
}
.hex-map-outer {
    width: 100%;
    min-height: 460px;
    max-height: 650px;
    overflow: auto;
    border: 1px solid #dee2e6;
    border-radius: 14px;
    background:
        radial-gradient(circle at 1px 1px, rgba(0,0,0,.045) 1px, transparent 0);
    background-size: 28px 28px;
    padding: 14px;
}
.hex-map {
    position: relative;
    background: transparent;
}
.empty-map {
    height: 420px;
    display:flex;
    align-items:center;
    justify-content:center;
    color:#868e96;
}
.link-layer {
    position:absolute;
    left:0;
    top:0;
    z-index:1;
    pointer-events:none;
}
.link-line {
    stroke:#adb5bd;
    stroke-width:2;
}
.hex-wrap {
    position:absolute;
    width:156px;
    height:136px;
    z-index:2;
    transform: rotate(var(--rot));
    transform-origin: 78px 68px;
}
.hex {
    width:156px;
    height:136px;
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
    margin-bottom:6px;
}
.hex-title {
    font-weight:700;
    color:#212529;
    font-size:14px;
    line-height:1.12;
    overflow-wrap:anywhere;
}
.unplaced {
    border: 1px dashed #adb5bd;
    border-radius: 12px;
    padding: 8px 10px;
    margin: 6px 0;
    background: #f8f9fa;
    font-size: 0.92rem;
}
.legend-dot {
    display:inline-block;
    width:12px;
    height:12px;
    border-radius:50%;
    margin-right:5px;
    vertical-align:-1px;
}
@media (max-width: 900px) {
    .hex-map-outer { max-height: 520px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# --- UI --------------------------------------------------------------------

st.title("RuokaVirta HexMap")
st.markdown('<div class="subtitle">Kevyt kuusikulmakartta työpajan keskusteluun. Lisää kortteja ja kytke ne toistensa sivuihin.</div>', unsafe_allow_html=True)

if st.session_state.message:
    st.success(st.session_state.message)

left, right = st.columns([0.8, 1.7], gap="large")

with left:
    st.subheader("1. Lisää kortti")

    with st.form("add_card_form", clear_on_submit=True):
        title = st.text_input("Kortin teksti", placeholder="esim. Pienet toimituserät")
        card_type = st.selectbox("Väri", list(TYPE_COLORS.keys()))
        with st.expander("Lisätieto, jos tarvitaan"):
            note = st.text_area("Muistiinpano")
        submitted = st.form_submit_button("Lisää")
        if submitted:
            add_card(title, card_type, note)
            st.rerun()

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Esimerkit"):
            add_examples()
            st.rerun()
    with b2:
        if st.button("Tyhjennä"):
            st.session_state.cards = []
            st.session_state.links = []
            st.session_state.next_id = 1
            st.session_state.message = "Kartta tyhjennetty."
            st.rerun()

    st.divider()

    st.subheader("2. Kytke sivuun")

    if len(st.session_state.cards) < 2:
        st.caption("Lisää vähintään kaksi korttia.")
    else:
        placed_cards = [c for c in st.session_state.cards if c.get("placed")]
        all_cards = st.session_state.cards

        source_options = {f'#{c["id"]} {c["title"]}': c["id"] for c in placed_cards}
        target_options = {f'#{c["id"]} {c["title"]}': c["id"] for c in all_cards}

        with st.form("connect_form"):
            source_label = st.selectbox("Mihin korttiin?", list(source_options.keys()))
            side = st.radio("Mille sivulle?", list(SIDES.keys()), horizontal=False)
            target_label = st.selectbox("Mikä kortti siihen tulee?", list(target_options.keys()))

            with st.expander("Tarkempi yhteys, jos tarvitaan"):
                rel_type = st.selectbox("Yhteyden tyyppi", REL_TYPES)
                explanation = st.text_area("Perustelu")
                force_move = st.checkbox("Siirrä, jos kortti on jo kartalla")
            submitted = st.form_submit_button("Kytke")
            if submitted:
                # Defaults when expander has not been touched
                rel_type = rel_type if "rel_type" in locals() else "liittyy"
                explanation = explanation if "explanation" in locals() else ""
                force_move = force_move if "force_move" in locals() else False
                connect_cards(source_options[source_label], target_options[target_label], side, rel_type, explanation, force_move)
                st.rerun()

    st.divider()

    st.subheader("Sijoittamattomat")
    unplaced = [c for c in st.session_state.cards if not c.get("placed")]
    if not unplaced:
        st.caption("Ei sijoittamattomia kortteja.")
    else:
        for c in unplaced:
            st.markdown(
                f'<div class="unplaced"><b>#{c["id"]} {html.escape(c["title"])}</b></div>',
                unsafe_allow_html=True,
            )

    with st.expander("Värit ja vienti"):
        for name, color in TYPE_COLORS.items():
            st.markdown(f'<span class="legend-dot" style="background:{color};"></span>{name}', unsafe_allow_html=True)

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

with right:
    st.subheader("Korttitila")
    render_map()

    with st.expander("Kirjatut yhteydet"):
        if not st.session_state.links:
            st.caption("Ei yhteyksiä vielä.")
        else:
            for link in st.session_state.links:
                a = get_card(link["from_card_id"])
                b = get_card(link["to_card_id"])
                if a and b:
                    st.markdown(
                        f'**#{a["id"]} {a["title"]}** → **#{b["id"]} {b["title"]}**  \n'
                        f'{link.get("relationship_type", "liittyy")} · {link.get("side", "")}'
                    )
                    if link.get("explanation"):
                        st.caption(link["explanation"])
