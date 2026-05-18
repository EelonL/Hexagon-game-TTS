
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
}

# Flat-top hex grid with two basis vectors:
# E  = (1, 0)
# SE = (0, 1)
# This makes the six side-neighbours unambiguous and easy to check.
SIDES = {
    "→ oikealle": (1, 0),
    "↗ yläoikealle": (1, -1),
    "↖ ylävasemmalle": (0, -1),
    "← vasemmalle": (-1, 0),
    "↙ alavasemmalle": (-1, 1),
    "↘ alaoikealle": (0, 1),
}

REL_TYPES = ["liittyy", "mahdollistaa", "estää", "vahvistaa", "heikentää"]

def init_state():
    if "cards" not in st.session_state:
        st.session_state.cards = []
    if "links" not in st.session_state:
        st.session_state.links = []
    if "next_id" not in st.session_state:
        st.session_state.next_id = 1
    if "message" not in st.session_state:
        st.session_state.message = ""
    if "error_message" not in st.session_state:
        st.session_state.error_message = ""
    if "last_source_id" not in st.session_state:
        st.session_state.last_source_id = None

init_state()

def set_success(msg):
    st.session_state.message = msg
    st.session_state.error_message = ""

def set_error(msg):
    st.session_state.error_message = msg
    st.session_state.message = ""

def get_card(card_id):
    return next((c for c in st.session_state.cards if c["id"] == card_id), None)

def card_pos(card):
    return (int(card.get("a", card.get("q", 0))), int(card.get("b", card.get("r", 0))))

def occupied_positions(exclude_id=None):
    positions = {}
    for c in st.session_state.cards:
        if exclude_id is not None and c["id"] == exclude_id:
            continue
        if c.get("placed"):
            positions[card_pos(c)] = c["id"]
    return positions

def migrate_old_coords():
    # Allows JSON/state from previous versions to keep working.
    for c in st.session_state.cards:
        if "a" not in c and "q" in c:
            c["a"] = c.get("q", 0)
        if "b" not in c and "r" in c:
            c["b"] = c.get("r", 0)

migrate_old_coords()

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
        "a": 0 if is_first else None,
        "b": 0 if is_first else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    set_success(f"Lisätty kortti #{card_id}")

def add_examples():
    if st.session_state.cards:
        set_error("Tyhjennä kartta ennen esimerkkien lisäämistä.")
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

    coords = [(0, 0), (1, 0), (1, -1), (0, -1), (-1, 0), (0, 1)]
    for c, (a, b) in zip(st.session_state.cards, coords):
        c["placed"] = True
        c["a"] = a
        c["b"] = b

    st.session_state.links = [
        {"from_card_id": 1, "to_card_id": 2, "side": "→ oikealle", "relationship_type": "vahvistaa", "explanation": ""},
        {"from_card_id": 1, "to_card_id": 3, "side": "↗ yläoikealle", "relationship_type": "mahdollistaa", "explanation": ""},
        {"from_card_id": 4, "to_card_id": 5, "side": "← vasemmalle", "relationship_type": "liittyy", "explanation": ""},
    ]
    set_success("Esimerkkikartta lisätty.")

def remove_links_involving(card_id):
    st.session_state.links = [
        l for l in st.session_state.links
        if l.get("from_card_id") != card_id and l.get("to_card_id") != card_id
    ]

def connect_cards(source_id, target_id, side, rel_type="liittyy", explanation="", force_move=False):
    if source_id == target_id:
        set_error("Valitse kaksi eri korttia.")
        return

    source = get_card(source_id)
    target = get_card(target_id)
    if source is None or target is None:
        set_error("Korttia ei löytynyt.")
        return

    if not source.get("placed"):
        source["placed"] = True
        source["a"] = 0
        source["b"] = 0

    source_a, source_b = card_pos(source)
    da, db = SIDES[side]
    new_a = source_a + da
    new_b = source_b + db

    # Important: always check the intended grid slot before moving anything.
    occupied = occupied_positions(exclude_id=target_id if force_move else None)
    if (new_a, new_b) in occupied:
        blocking_id = occupied[(new_a, new_b)]
        blocking = get_card(blocking_id)
        blocking_title = blocking["title"] if blocking else ""
        set_error(
            f"Paikka on jo varattu: kortin #{source_id} sivulla '{side}' on jo "
            f"kortti #{blocking_id} {blocking_title}. Valitse toinen sivu."
        )
        return

    if target.get("placed") and not force_move:
        set_error("Kohdekortti on jo kartalla. Valitse siirto vain, jos haluat siirtää sen uuteen kohtaan.")
        return

    if force_move:
        remove_links_involving(target_id)

    target["placed"] = True
    target["a"] = new_a
    target["b"] = new_b

    st.session_state.links.append({
        "from_card_id": source_id,
        "to_card_id": target_id,
        "side": side,
        "relationship_type": rel_type,
        "explanation": explanation.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    st.session_state.last_source_id = source_id
    set_success(f"Kytketty #{target_id} kortin #{source_id} sivuun {side}.")

# --- Drawing ---------------------------------------------------------------

HEX_W = 150
HEX_H = 129.9
GAP = 12

# Regular flat-top hex dimensions:
# side length s = HEX_W / 2
# height = sqrt(3) * s
# neighbour E center dx = 1.5*s = 0.75*HEX_W
# neighbour SE center dx = 0.75*s = 0.375*HEX_W, dy = HEX_H/2
DX_E = HEX_W * 0.75 + GAP
DX_SE = HEX_W * 0.375 + GAP * 0.5
DY_SE = HEX_H * 0.5 + GAP * 0.5

def hex_to_pixel(a, b):
    x = a * DX_E + b * DX_SE
    y = b * DY_SE
    return x, y

def map_bounds(cards):
    placed = [c for c in cards if c.get("placed")]
    if not placed:
        return 0, 0, 760, 440

    points = [hex_to_pixel(*card_pos(c)) for c in placed]
    min_x = min(x for x, _ in points) - 170
    max_x = max(x for x, _ in points) + 340
    min_y = min(y for _, y in points) - 170
    max_y = max(y for _, y in points) + 310

    return min_x, min_y, max(760, int(max_x - min_x)), max(440, int(max_y - min_y))

def card_html(card, min_x, min_y):
    a, b = card_pos(card)
    x, y = hex_to_pixel(a, b)
    left = x - min_x
    top = y - min_y
    bg = TYPE_COLORS.get(card.get("type", "Havainto"), "#f1f3f5")
    title = html.escape(card.get("title", ""))

    # No visual rotation. This keeps the hexagons symmetric and text horizontal.
    return (
        f'<div class="hex-wrap" style="left:{left}px; top:{top}px;">'
        f'<div class="hex" style="background:{bg};">'
        f'<div class="hex-inner">'
        f'<div class="hex-id">#{card["id"]}</div>'
        f'<div class="hex-title">{title}</div>'
        f'</div></div></div>'
    )

def side_midpoint(card, side, min_x, min_y):
    x, y = hex_to_pixel(*card_pos(card))
    cx = x - min_x + HEX_W / 2
    cy = y - min_y + HEX_H / 2

    offsets = {
        "→ oikealle": (HEX_W * 0.50, 0),
        "↗ yläoikealle": (HEX_W * 0.25, -HEX_H * 0.50),
        "↖ ylävasemmalle": (-HEX_W * 0.25, -HEX_H * 0.50),
        "← vasemmalle": (-HEX_W * 0.50, 0),
        "↙ alavasemmalle": (-HEX_W * 0.25, HEX_H * 0.50),
        "↘ alaoikealle": (HEX_W * 0.25, HEX_H * 0.50),
    }
    dx, dy = offsets.get(side, (0, 0))
    return cx + dx, cy + dy

def opposite_side(side):
    return {
        "→ oikealle": "← vasemmalle",
        "↗ yläoikealle": "↙ alavasemmalle",
        "↖ ylävasemmalle": "↘ alaoikealle",
        "← vasemmalle": "→ oikealle",
        "↙ alavasemmalle": "↗ yläoikealle",
        "↘ alaoikealle": "↖ ylävasemmalle",
    }.get(side, "← vasemmalle")

def link_svg(link, min_x, min_y):
    a = get_card(link["from_card_id"])
    b = get_card(link["to_card_id"])
    if not a or not b or not a.get("placed") or not b.get("placed"):
        return ""

    side = link.get("side", "→ oikealle")
    x1, y1 = side_midpoint(a, side, min_x, min_y)
    x2, y2 = side_midpoint(b, opposite_side(side), min_x, min_y)

    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="link-line" />'
        f'<circle cx="{x1}" cy="{y1}" r="4" class="link-dot" />'
        f'<circle cx="{x2}" cy="{y2}" r="4" class="link-dot" />'
    )

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

st.markdown(
    """
<style>
.block-container { padding-top: 1.5rem; max-width: 1500px; }
h1 { margin-bottom: 0.2rem; }
.subtitle { color:#6c757d; margin-bottom: 1.2rem; }
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
.hex-map { position: relative; background: transparent; }
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
    stroke:#748ffc;
    stroke-width:3;
    stroke-linecap:round;
}
.link-dot {
    fill:#748ffc;
    stroke:white;
    stroke-width:2;
}
.hex-wrap {
    position:absolute;
    width:150px;
    height:129.9px;
    z-index:2;
}
.hex {
    width:150px;
    height:129.9px;
    clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
    display:flex;
    align-items:center;
    justify-content:center;
    box-shadow: 0 1px 2px rgba(0,0,0,.08);
}
.hex-inner {
    width:110px;
    text-align:center;
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

st.title("RuokaVirta HexMap")
st.markdown('<div class="subtitle">Kevyt kuusikulmakartta työpajan keskusteluun. Lisää kortteja ja kytke ne toistensa sivuihin.</div>', unsafe_allow_html=True)

if st.session_state.error_message:
    st.error(st.session_state.error_message)
elif st.session_state.message:
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
            st.session_state.error_message = ""
            st.session_state.last_source_id = None
            st.rerun()

    st.divider()
    st.subheader("2. Kytke sivuun")

    if len(st.session_state.cards) < 2:
        st.caption("Lisää vähintään kaksi korttia.")
    else:
        placed_cards = [c for c in st.session_state.cards if c.get("placed")]
        all_cards = st.session_state.cards

        source_labels = [f'#{c["id"]} {c["title"]}' for c in placed_cards]
        source_ids = [c["id"] for c in placed_cards]
        default_source_index = 0
        if st.session_state.last_source_id in source_ids:
            default_source_index = source_ids.index(st.session_state.last_source_id)

        target_labels = [f'#{c["id"]} {c["title"]}' for c in all_cards]
        target_ids = [c["id"] for c in all_cards]

        with st.form("connect_form"):
            source_label = st.selectbox("Mihin korttiin?", source_labels, index=default_source_index)
            side = st.radio("Mille sivulle?", list(SIDES.keys()), horizontal=False)
            target_label = st.selectbox("Mikä kortti siihen tulee?", target_labels)

            with st.expander("Tarkempi yhteys, jos tarvitaan"):
                rel_type = st.selectbox("Yhteyden tyyppi", REL_TYPES)
                explanation = st.text_area("Perustelu")
                force_move = st.checkbox("Siirrä, jos kortti on jo kartalla")
            submitted = st.form_submit_button("Kytke")
            if submitted:
                connect_cards(
                    source_ids[source_labels.index(source_label)],
                    target_ids[target_labels.index(target_label)],
                    side,
                    rel_type,
                    explanation,
                    force_move,
                )
                st.rerun()

    st.divider()
    st.subheader("Sijoittamattomat")
    unplaced = [c for c in st.session_state.cards if not c.get("placed")]
    if not unplaced:
        st.caption("Ei sijoittamattomia kortteja.")
    else:
        for c in unplaced:
            st.markdown(f'<div class="unplaced"><b>#{c["id"]} {html.escape(c["title"])}</b></div>', unsafe_allow_html=True)

    with st.expander("Värit ja vienti"):
        for name, color in TYPE_COLORS.items():
            st.markdown(f'<span class="legend-dot" style="background:{color};"></span>{name}', unsafe_allow_html=True)

        st.download_button("Lataa JSON", data=export_json(), file_name="ruokavirta_hexmap.json", mime="application/json")

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
