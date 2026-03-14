# app.py
# Google Form Injector — Main Streamlit Application
# ============================================================
# Layout:
#   Sidebar  : Form URL · Delay · Metadata · Generator Reference
#   Tab 1    : Upload CSV & Preview
#   Tab 2    : Mapping Builder (with Decode Raw Payload)
#   Tab 3    : Injection → Progress → Log → Results → Export
# ============================================================

import json
import random
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from utils.csv_handler import (
    dataframe_to_records,
    get_column_names,
    get_column_stats,
    get_preview,
    get_row_count,
    load_csv,
)
from utils.form_handler import (
    ALL_MODES,
    MODE_CSV,
    MODE_GENERATOR,
    MODE_STATIC,
    build_payload,
    decode_raw_payload,
    is_valid_form_url,
    normalise_form_url,
    run_bulk_submit,
    summarise_results,
    validate_mappings,
)
from utils.generators import (
    get_generator_description,
    get_generator_names,
    get_generator_sample,
    get_random_choice,
    get_random_float,
    get_random_integer,
    register_generator,
    unregister_generator,
)

st.set_page_config(
    page_title="Google Form Injector",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.4rem; padding-bottom: 2rem; }

    /* Mapping card */
    .mapping-card {
        background: #1a1b26;
        border: 1px solid #2e3147;
        border-radius: 10px;
        padding: 0.85rem 1.1rem 0.5rem 1.1rem;
        margin-bottom: 0.75rem;
    }

    /* Log panel */
    .log-box {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-family: "Courier New", monospace;
        font-size: 0.8rem;
        max-height: 380px;
        overflow-y: auto;
        line-height: 1.7;
        white-space: pre-wrap;
        word-break: break-all;
    }

    /* Section header */
    .section-header {
        font-size: 1rem;
        font-weight: 700;
        color: #cdd6f4;
        border-left: 4px solid #89b4fa;
        padding-left: 0.6rem;
        margin: 1.1rem 0 0.5rem 0;
    }

    /* Sidebar footer */
    .sidebar-footer {
        font-size: 0.68rem;
        color: #6c7086;
        text-align: center;
        margin-top: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Session-state initialisation
# ============================================================


def _init_state() -> None:
    """Initialise all required session-state keys exactly once."""
    defaults: dict = {
        "df": None,
        "csv_columns": [],
        "mappings": [],
        "next_mapping_id": 0,
        "is_running": False,
        "stop_flag": [False],
        "results": [],
        "log_lines": [],
        "show_payload_preview": False,
        "agreed": False,
        "fvv_val": "1",
        "ph_val": "0",
        "decoded_result": None,
        "raw_payload_text": "",
        "custom_generators": {},
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()

# Register custom generators on every rerun
for gen_name, gen_data in st.session_state.custom_generators.items():
    if gen_data["type"] == "Options List":
        register_generator(
            gen_name,
            func=get_random_choice,
            kwargs={"options": gen_data["options"]},
            description=f"Custom list ({len(gen_data['options'])} items)",
            sample=lambda opts=gen_data["options"]: get_random_choice(opts),
        )
    elif gen_data["type"] == "Integer Range":
        register_generator(
            gen_name,
            func=get_random_integer,
            kwargs={"min_val": gen_data["min"], "max_val": gen_data["max"]},
            description=f"Integer between {gen_data['min']} and {gen_data['max']}",
            sample=lambda m1=gen_data["min"], m2=gen_data["max"]: get_random_integer(m1, m2),
        )
    elif gen_data["type"] == "Float Range":
        register_generator(
            gen_name,
            func=get_random_float,
            kwargs={"min_val": gen_data["min"], "max_val": gen_data["max"], "decimals": 2},
            description=f"Float between {gen_data['min']} and {gen_data['max']}",
            sample=lambda m1=gen_data["min"], m2=gen_data["max"]: get_random_float(m1, m2, 2),
        )

if not st.session_state.agreed:
    
    def _agreed_callback():
        st.session_state.agreed = True
        st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog("⚠️ Terms of Use Agreement")
        def show_agreement():
            st.warning("This application is specifically made for **testing and educational purposes**.")
            st.markdown(
                "By using this application, you agree that:\n"
                "- You have permission to submit data to the target form.\n"
                "- The developer is not responsible for any misuse of this tool.\n"
                "- You will not use it to intentionally cause harm (e.g., spamming)."
            )
            if st.button("I Agree", type="primary", use_container_width=True):
                _agreed_callback()
        show_agreement()
    else:
        st.markdown("## ⚠️ Terms of Use Agreement")
        st.warning("This application is specifically made for **testing and educational purposes**.")
        st.markdown(
            "By using this application, you agree that:\n"
            "- You have permission to submit data to the target form.\n"
            "- The developer is not responsible for any misuse of this tool.\n"
            "- You will not use it to intentionally cause harm (e.g., spamming)."
        )
        if st.button("I Agree", type="primary"):
            _agreed_callback()
    
    st.stop()

# ============================================================
# Helpers
# ============================================================

def _new_mapping(
    entry_id: str = "",
    mode: str = MODE_CSV,
    value: str = "",
    sentinel: bool = False,
) -> dict:
    """Return a fresh mapping dict with a unique auto-increment id."""
    uid = st.session_state.next_mapping_id
    st.session_state.next_mapping_id += 1
    return {
        "id": uid,
        "entry_id": entry_id,
        "mode": mode,
        "value": value,
        "sentinel": sentinel,
    }


def _colourise_log(line: str) -> str:
    """Wrap a log line in a colour-coded HTML <span>."""
    if "✅" in line:
        colour = "#a6e3a1"  
    elif "❌" in line:
        colour = "#f38ba8"  
    elif "⏹" in line:
        colour = "#fab387"  
    elif "🧪" in line or "DRY" in line:
        colour = "#89dceb"  
    elif "⚠" in line:
        colour = "#f9e2af" 
    elif "🚀" in line or "Start" in line:
        colour = "#b4befe" 
    else:
        colour = "#cdd6f4" 

    safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<span style='color:{colour}'>{safe}</span>"


def _render_log(lines: list[str]) -> None:
    """Render the full log list inside a styled scrollable box (newest first)."""
    if not lines:
        return
    html_lines = "<br>".join(_colourise_log(ln) for ln in reversed(lines))
    st.markdown(f"<div class='log-box'>{html_lines}</div>", unsafe_allow_html=True)


def _sh(text: str) -> None:
    """Render a styled section header."""
    st.markdown(f"<div class='section-header'>{text}</div>", unsafe_allow_html=True)


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:
    try:
        st.image(
            "./img/logo.png",
            width=200,
        )
    except Exception:
        st.markdown("🚀")

    st.title("GForm Injector")
    st.caption("Automatically submit CSV data to Google Forms")

    st.warning("**Warning:** Developer is not responsible for any misuse of this tool.")

    # ── Generator Reference ───────────────────────────────────
    with st.expander("Generator Reference", expanded=False):
        for gen_name in get_generator_names():
            desc = get_generator_description(gen_name)
            sample = get_generator_sample(gen_name)
            st.markdown(
                f"**{gen_name}**  \n"
                f"<span style='color:#a6e3a1;font-size:0.77rem'>{desc}</span>  \n"
                f"<span style='color:#89dceb;font-size:0.75rem'>Example: `{sample}`</span>",
                unsafe_allow_html=True,
            )
            st.divider()

    st.markdown(
        "<div class='sidebar-footer'>Made with ❤️ by NDFProject</div>",
        unsafe_allow_html=True,
    )

# ============================================================
# Page title
# ============================================================

st.markdown("## Google Form Injector")
st.caption("Upload a CSV · Configure field mappings · Bulk-submit to Google Forms")

tab_upload, tab_mapping, tab_inject = st.tabs(
    ["Upload & Preview", "Mapping Builder", "Injection"]
)

# ============================================================
# TAB 1 — Upload & Preview
# ============================================================

with tab_upload:
    _sh("Form URL")
    
    raw_url: str = st.text_input(
        "Response URL",
        placeholder="https://docs.google.com/forms/d/e/.../formResponse",
        help=(
            "Must end with `/formResponse`.\n"
            "A `/viewform` URL will be converted automatically."
        ),
        label_visibility="collapsed",
    )

    form_url = ""
    url_valid = False
    if raw_url.strip():
        form_url = normalise_form_url(raw_url)
        url_valid = is_valid_form_url(form_url)
        if url_valid:
            st.success("URL is valid")
        else:
            st.error("Invalid URL — must be `docs.google.com/forms/...`")
        with st.expander("Resolved URL", expanded=False):
            st.code(form_url, language=None)

    st.divider()

    _sh("⬆️ Upload CSV File")

    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=["csv"],
        help="The file must have a header row in the first line.",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        with st.spinner("Reading CSV file…"):
            try:
                df_loaded = load_csv(uploaded_file)
                if df_loaded is not None and not df_loaded.empty:
                    st.session_state.df = df_loaded
                    st.session_state.csv_columns = get_column_names(df_loaded)
                    st.success(
                        f"File loaded — "
                        f"**{get_row_count(df_loaded):,} rows** × "
                        f"**{len(st.session_state.csv_columns)} columns**"
                    )
                else:
                    st.error("❌ CSV file is empty or could not be parsed.")
            except ValueError as exc:
                st.error(f"❌ {exc}")

    if st.session_state.df is not None:
        _df = st.session_state.df

        # ── Summary metrics ───────────────────────────────────
        _sh("Dataset Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Rows", f"{get_row_count(_df):,}")
        m2.metric("Total Columns", len(st.session_state.csv_columns))
        m3.metric("Missing Values", int(_df.isnull().sum().sum()))
        m4.metric("Duplicate Rows", int(_df.duplicated().sum()))

        st.markdown("<br>", unsafe_allow_html=True)
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.caption("Missing Values per Column")
            st.bar_chart(_df.isnull().sum(), height=250)
        with chart_col2:
            st.caption("Unique Values per Column")
            st.bar_chart(_df.nunique(), height=250)

        # ── Column chips ──────────────────────────────────────
        _sh("Column Names")
        col_names = st.session_state.csv_columns
        cols_per_row = 4
        for i in range(0, len(col_names), cols_per_row):
            chunk = col_names[i : i + cols_per_row]
            grid = st.columns(cols_per_row)
            for j, cname in enumerate(chunk):
                grid[j].code(cname)

        # ── Preview table ─────────────────────────────────────
        _sh("Data Preview")
        n_prev = st.slider(
            "Rows to preview",
            min_value=1,
            max_value=min(100, get_row_count(_df)),
            value=5,
        )
        st.dataframe(get_preview(_df, n_prev), use_container_width=True)

        # ── Column statistics ─────────────────────────────────
        with st.expander("Column Statistics", expanded=False):
            stats_list = get_column_stats(_df)
            stats_df = pd.DataFrame(stats_list).rename(
                columns={
                    "name": "Column",
                    "dtype": "Type",
                    "non_null": "Non-Null",
                    "unique": "Unique",
                    "sample": "Sample Values",
                }
            )
            st.dataframe(stats_df, use_container_width=True, hide_index=True)

    else:
        st.info(
            "Upload a CSV file above to get started.\n\n"
            "The file must be in `.csv` format with a header row on the first line.",
            icon="ℹ️",
        )


# ============================================================
# TAB 2 — Mapping Builder
# ============================================================

with tab_mapping:
    _sh("🗺️ Entry Mapping Configuration")

    # ── Custom Generators ─────────────────────────────────────
    with st.expander("⚙️ Custom Generators", expanded=False):
        cg_action = st.radio("Action", ["Add New", "Manage Existing"], horizontal=True, label_visibility="collapsed")
        
        if cg_action == "Add New":
            cg_name = st.text_input("Generator Name", placeholder="e.g. My Custom Range")
            cg_type = st.selectbox("Generator Type", ["Options List", "Integer Range", "Float Range"])
            
            cg_opts = []
            cg_min = 0
            cg_max = 100
            
            if cg_type == "Options List":
                cg_opts_raw = st.text_area("Options (comma-separated)", placeholder="Apple, Banana, Cherry")
                cg_opts = [x.strip() for x in cg_opts_raw.split(",") if x.strip()]
            else:
                col1, col2 = st.columns(2)
                with col1:
                    cg_min = st.number_input("Min", value=0)
                with col2:
                    cg_max = st.number_input("Max", value=100)
                    
            if st.button("Save Generator", use_container_width=True, type="primary"):
                if not cg_name.strip():
                    st.error("Name cannot be empty.")
                elif cg_name.strip() in get_generator_names() and cg_name.strip() not in st.session_state.custom_generators:
                    st.error("Name conflicts with a built-in generator.")
                elif cg_type == "Options List" and not cg_opts:
                    st.error("Please provide at least one option.")
                elif cg_type in ["Integer Range", "Float Range"] and cg_min > cg_max:
                    st.error("Min cannot be greater than Max.")
                else:
                    st.session_state.custom_generators[cg_name.strip()] = {
                        "type": cg_type,
                        "options": cg_opts,
                        "min": cg_min,
                        "max": cg_max
                    }
                    st.success(f"Saved '{cg_name.strip()}'!")
                    time.sleep(1)
                    st.rerun()

        else:
            if not st.session_state.custom_generators:
                st.info("No custom generators added yet.")
            else:
                for cname in list(st.session_state.custom_generators.keys()):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.write(f"**{cname}**")
                    with c2:
                        if st.button("🗑️", key=f"del_cg_{cname}", help="Delete"):
                            del st.session_state.custom_generators[cname]
                            unregister_generator(cname)
                            st.rerun()

    # ── DECODE RAW PAYLOAD ────────────────────────────────────
    with st.expander("🔓 Decode Raw Payload → Auto-fill Mapping", expanded=False):
        st.markdown(
            "Paste the **raw payload** captured from your browser's DevTools "
            "(Network tab → Request Body). The app will extract all `entry.XXXX` "
            "fields and populate the mapping table automatically."
        )

        raw_input = st.text_area(
            "Raw Payload",
            value=st.session_state.raw_payload_text,
            height=110,
            placeholder=(
                "entry.37854030=tt&entry.1095224243=12&entry.562465567=test"
                "&entry.1013225845=test&entry.235502927=test"
                "&fvv=1&pageHistory=0&entry.1013225845_sentinel=&entry.235502927_sentinel="
            ),
            label_visibility="collapsed",
            key="raw_payload_input",
        )

        dc1, dc2, dc3, dc4 = st.columns([1.2, 1.5, 1.5, 2.5])

        with dc1:
            decode_btn = st.button(
                "Decode",
                use_container_width=True,
                help="Parse the payload and display the decoded fields",
            )
        with dc2:
            append_btn = st.button(
                "Append to Mapping",
                use_container_width=True,
                disabled=st.session_state.decoded_result is None,
                help="Add decoded entries to the existing mapping list",
            )
        with dc3:
            replace_btn = st.button(
                "Replace All Mappings",
                use_container_width=True,
                disabled=st.session_state.decoded_result is None,
                help="Clear all current mappings and replace with decoded entries",
            )
        with dc4:
            if st.session_state.decoded_result is not None:
                n = st.session_state.decoded_result.get("total_entries", 0)
                st.caption(f"Decoded: **{n} entries** ready to import")

        # ── Run decoder ───────────────────────────────────────
        if decode_btn:
            raw_text = raw_input.strip()
            st.session_state.raw_payload_text = raw_text
            if not raw_text:
                st.warning("Please paste a raw payload first.", icon="⚠️")
            else:
                try:
                    result = decode_raw_payload(raw_text)
                    st.session_state.decoded_result = result
                    if result["total_entries"] == 0:
                        st.warning(
                            "No `entry.*` fields found in the payload.",
                            icon="⚠️",
                        )
                    else:
                        st.success(
                            f"Decoded **{result['total_entries']} entries**, "
                            f"**{len(result['sentinel_ids'])} sentinels**, "
                            f"fvv=`{result['fvv']}`, "
                            f"pageHistory=`{result['page_history']}`",
                            icon="✅",
                        )
                except Exception as exc:
                    st.error(f"❌ Decode failed: {exc}")
                    st.session_state.decoded_result = None

        # ── Append action ─────────────────────────────────────
        if append_btn and st.session_state.decoded_result is not None:
            _res = st.session_state.decoded_result
            _added = 0
            for _e in _res["entries"]:
                st.session_state.mappings.append(
                    _new_mapping(
                        entry_id=_e["entry_id"],
                        mode=MODE_STATIC,
                        value=_e["value"],
                        sentinel=_e["sentinel"],
                    )
                )
                _added += 1
            st.session_state.fvv_val = _res["fvv"]
            st.session_state.ph_val = _res["page_history"]
            st.success(
                f"✅ **{_added} mappings** appended. "
                f"fvv & pageHistory updated in the Sidebar.",
                icon="✅",
            )
            st.rerun()

        # ── Replace action ────────────────────────────────────
        if replace_btn and st.session_state.decoded_result is not None:
            _res = st.session_state.decoded_result
            st.session_state.mappings = []
            st.session_state.next_mapping_id = 0
            for _e in _res["entries"]:
                st.session_state.mappings.append(
                    _new_mapping(
                        entry_id=_e["entry_id"],
                        mode=MODE_STATIC,
                        value=_e["value"],
                        sentinel=_e["sentinel"],
                    )
                )
            st.session_state.fvv_val = _res["fvv"]
            st.session_state.ph_val = _res["page_history"]
            st.success(
                f"Mappings replaced with **{len(_res['entries'])} new entries**. "
                f"fvv & pageHistory updated in the Sidebar.",
                icon="✅",
            )
            st.rerun()

        # ── Preview decoded result ────────────────────────────
        if st.session_state.decoded_result is not None:
            _res = st.session_state.decoded_result
            if _res["total_entries"] > 0:
                st.divider()
                _sh("Decode Result")

                _entry_rows = []
                for _e in _res["entries"]:
                    _entry_rows.append(
                        {
                            "Entry ID": _e["entry_id"],
                            "Sample Value": _e["value"],
                            "Sentinel": "✅" if _e["sentinel"] else "—",
                        }
                    )
                st.dataframe(
                    pd.DataFrame(_entry_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                _mcol1, _mcol2 = st.columns(2)
                with _mcol1:
                    st.markdown("**Form Metadata**")
                    st.table(
                        pd.DataFrame(
                            [
                                {"Key": "fvv", "Value": _res["fvv"]},
                                {"Key": "pageHistory", "Value": _res["page_history"]},
                            ]
                        )
                    )
                with _mcol2:
                    if _res["google_internal"]:
                        st.markdown("**Google Internal Fields**")
                        _gi_rows = [
                            {"Key": k, "Value": str(v)[:60]}
                            for k, v in _res["google_internal"].items()
                        ]
                        st.table(pd.DataFrame(_gi_rows))

                if _res["metadata"]:
                    with st.expander("🗃️ Other Fields", expanded=False):
                        st.json(_res["metadata"])

    st.divider()

    # ── CSV status banner ─────────────────────────────────────
    csv_columns = st.session_state.csv_columns
    gen_names = get_generator_names()

    if st.session_state.df is None:
        st.info(
            "Upload a CSV file in the **Upload & Preview** tab to enable "
            "**CSV Column** mode in the mapping editor.",
            icon="ℹ️",
        )

    # ── Toolbar ───────────────────────────────────────────────
    tb1, tb2, tb3, tb4 = st.columns([1.2, 1.2, 1.5, 2.5])

    with tb1:
        if st.button(
            "➕ Add Row", use_container_width=True, help="Add a new mapping row"
        ):
            st.session_state.mappings.append(_new_mapping())
            st.rerun()

    with tb2:
        if st.button("🗑️ Clear All", use_container_width=True):
            st.session_state.mappings = []
            st.rerun()

    with tb3:
        if st.button(
            "⚡ Auto-fill from CSV",
            use_container_width=True,
            disabled=st.session_state.df is None,
            help="Create one mapping row per CSV column (requires CSV upload)",
        ):
            for col in csv_columns:
                st.session_state.mappings.append(
                    _new_mapping(entry_id="entry.", mode=MODE_CSV, value=col)
                )
            st.rerun()

    with tb4:
        st.caption(
            f"Active mappings: **{len(st.session_state.mappings)}** | "
            f"CSV columns: **{len(csv_columns)}**"
        )

    st.divider()

    # ── Per-mapping editor ────────────────────────────────────
    indices_to_delete: list[int] = []

    for i, mapping in enumerate(st.session_state.mappings):
        mid = mapping["id"]

        st.markdown("<div class='mapping-card'>", unsafe_allow_html=True)

        hdr, del_btn_col = st.columns([11, 1])
        with hdr:
            st.markdown(
                f"<span style='color:#89b4fa;font-weight:700'>Mapping #{i + 1}</span>",
                unsafe_allow_html=True,
            )
        with del_btn_col:
            if st.button("✕", key=f"del_{mid}", help="Remove this mapping"):
                indices_to_delete.append(i)

        c1, c2, c3, c4 = st.columns([2.6, 1.8, 3.2, 1.4])

        with c1:
            new_eid = st.text_input(
                "Entry ID",
                value=mapping["entry_id"],
                placeholder="entry.123456789",
                key=f"eid_{mid}",
                help="Format: `entry.<number>`, e.g. `entry.976363616`",
            )
            mapping["entry_id"] = new_eid

        with c2:
            mode_idx = (
                ALL_MODES.index(mapping["mode"]) if mapping["mode"] in ALL_MODES else 0
            )
            new_mode = st.selectbox(
                "Mode",
                options=ALL_MODES,
                index=mode_idx,
                key=f"mode_{mid}",
            )
            mapping["mode"] = new_mode

        with c3:
            if new_mode == MODE_CSV:
                if csv_columns:
                    cur_idx = (
                        csv_columns.index(mapping["value"])
                        if mapping["value"] in csv_columns
                        else 0
                    )
                    new_val = st.selectbox(
                        "CSV Column",
                        options=csv_columns,
                        index=cur_idx,
                        key=f"val_{mid}",
                    )
                    mapping["value"] = new_val
                else:
                    st.warning("Upload a CSV file to use this mode.", icon="⚠️")
                    new_val = st.text_input(
                        "CSV Column",
                        value=mapping["value"],
                        placeholder="(no CSV loaded)",
                        key=f"val_{mid}",
                        disabled=True,
                    )

            elif new_mode == MODE_STATIC:
                new_val = st.text_input(
                    "Static Value",
                    value=mapping["value"],
                    placeholder="Enter a fixed value…",
                    key=f"val_{mid}",
                )
                mapping["value"] = new_val

            else:  
                gen_idx = (
                    gen_names.index(mapping["value"])
                    if mapping["value"] in gen_names
                    else 0
                )
                new_val = st.selectbox(
                    "Generator",
                    options=gen_names,
                    index=gen_idx,
                    key=f"val_{mid}",
                )
                mapping["value"] = new_val
                st.caption(f"ℹ️ {get_generator_description(new_val)}")

        with c4:
            new_sent = st.checkbox(
                "Sentinel",
                value=mapping["sentinel"],
                key=f"sent_{mid}",
                help="Append `entry.XXX_sentinel = ''` for this field",
            )
            mapping["sentinel"] = new_sent

            if new_mode == MODE_GENERATOR and mapping["value"]:
                st.caption(f"`{get_generator_sample(mapping['value'])}`")
            elif new_mode == MODE_STATIC:
                st.caption(f"`{(mapping['value'] or '')[:22]}`")
            elif new_mode == MODE_CSV and mapping["value"] in csv_columns:
                try:
                    first_val = str(st.session_state.df.iloc[0][mapping["value"]])
                    st.caption(f"`{first_val[:22]}`")
                except Exception:
                    pass

        st.markdown("</div>", unsafe_allow_html=True)

    for idx in sorted(indices_to_delete, reverse=True):
        st.session_state.mappings.pop(idx)
    if indices_to_delete:
        st.rerun()

    # ── Validation banner ─────────────────────────────────────
    if st.session_state.mappings:
        issues = validate_mappings(st.session_state.mappings, csv_columns)
        if issues:
            _sh("Mapping Warnings")
            for iss in issues:
                st.warning(f"**{iss['entry_id']}** — {iss['issue']}", icon="⚠️")
        else:
            st.success(
                f"All {len(st.session_state.mappings)} mappings are valid.",
                icon="✅",
            )

    # ── Save / Load JSON ──────────────────────────────────────
    with st.expander("Save / Load Mapping Configuration (JSON)", expanded=False):
        exp_col, imp_col = st.columns(2)

        with exp_col:
            st.markdown("**Export**")
            if st.session_state.mappings:
                export_json = json.dumps(
                    [
                        {k: v for k, v in m.items() if k != "id"}
                        for m in st.session_state.mappings
                    ],
                    indent=2,
                    ensure_ascii=False,
                )
                st.download_button(
                    "Download mapping_config.json",
                    data=export_json,
                    file_name="mapping_config.json",
                    mime="application/json",
                    use_container_width=True,
                )
            else:
                st.caption("No mappings to export.")

        with imp_col:
            st.markdown("**Import**")
            json_file = st.file_uploader(
                "Upload JSON",
                type=["json"],
                key="json_import",
                label_visibility="collapsed",
            )
            if json_file is not None:
                try:
                    imported = json.loads(json_file.read().decode("utf-8"))
                    if isinstance(imported, list):
                        st.session_state.mappings = [
                            _new_mapping(
                                entry_id=m.get("entry_id", ""),
                                mode=m.get("mode", MODE_CSV),
                                value=m.get("value", ""),
                                sentinel=m.get("sentinel", False),
                            )
                            for m in imported
                        ]
                        st.success(f"{len(imported)} mappings loaded.", icon="✅")
                        st.rerun()
                    else:
                        st.error("Invalid JSON format (must be an array).")
                except Exception as exc:
                    st.error(f"Failed to read JSON: {exc}")


# ============================================================
# TAB 3 — Injection
# ============================================================

with tab_inject:
    # ── Pre-flight checklist ──────────────────────────────────
    _sh("Pre-flight Checklist")

    chk_csv = st.session_state.df is not None
    chk_map = len(st.session_state.mappings) > 0
    chk_url = url_valid

    cc1, cc2, cc3 = st.columns(3)
    cc1.metric(
        "Dataset",
        "Ready" if chk_csv else "Not uploaded",
        delta=f"{get_row_count(st.session_state.df):,} rows" if chk_csv else None,
    )
    cc2.metric(
        "Mapping",
        "Ready" if chk_map else "Not configured",
        delta=f"{len(st.session_state.mappings)} entries" if chk_map else None,
    )
    cc3.metric(
        "Form URL",
        "Valid" if chk_url else "Invalid",
        delta="/formResponse" if chk_url else None,
    )

    ready = chk_csv and chk_map and chk_url

    if not ready:
        missing = []
        if not chk_csv:
            missing.append("• Upload a CSV file in the **Upload & Preview** tab")
        if not chk_map:
            missing.append(
                "• Create at least one mapping in the **Mapping Builder** tab"
            )
        if not chk_url:
            missing.append("• Enter a valid Google Form URL in the **Sidebar**")
        st.info(
            "Complete the following steps before starting injection:\n\n"
            + "\n".join(missing),
            icon="ℹ️",
        )

    if ready:
        _sh("Row Range")
        total_rows = get_row_count(st.session_state.df)
        rng1, rng2, rng3 = st.columns([2, 2, 3])
        with rng1:
            start_row = st.number_input(
                "Start row (0-indexed)",
                min_value=0,
                max_value=max(0, total_rows - 1),
                value=0,
                step=1,
            )
        with rng2:
            end_row = st.number_input(
                "End row",
                min_value=1,
                max_value=total_rows,
                value=total_rows,
                step=1,
            )
        with rng3:
            selected_count = max(0, int(end_row) - int(start_row))
            st.metric("Rows to submit", f"{selected_count:,}")

        # Fetch settings for preview/injection. If not in UI anymore, use session state defaults
        current_fvv = st.session_state.get("fvv_val", "1")
        current_ph = st.session_state.get("ph_val", "0")
        
        # We need `include_sentinels` before it is defined in the UI
        # Check session state or set a reasonable default.
        if "include_sentinels_val" not in st.session_state:
            st.session_state.include_sentinels_val = True

        _sh("Payload Preview")
        prev_btn_col, _ = st.columns([1, 3])
        with prev_btn_col:
            if st.button("Generate Preview", use_container_width=True):
                st.session_state.show_payload_preview = True

        if st.session_state.show_payload_preview:
            _records_prev = dataframe_to_records(
                st.session_state.df.iloc[int(start_row) : int(end_row)]
            )
            if _records_prev:
                _sample_payload = build_payload(
                    row=_records_prev[0],
                    mappings=st.session_state.mappings,
                    fvv=current_fvv,
                    page_history=current_ph,
                    include_sentinels=st.session_state.include_sentinels_val,
                )
                st.caption("Payload for the **first row** of the selected range:")
                st.json(_sample_payload)
                with st.expander("URL-encoded (raw)", expanded=False):
                    st.code(
                        "&".join(f"{k}={v}" for k, v in _sample_payload.items()),
                        language=None,
                    )

        # ── Injection options ─────────────────────────────────
        _sh("Options")
        
        # ── Form Metadata ─────────────────────────────────────────
        with st.expander("Form Metadata", expanded=False):
            st.info("Only change this if you know what you are doing. Values are auto-filled by Decode Payload.")
            fm_c1, fm_c2 = st.columns(2)
            with fm_c1:
                fvv: str = st.text_input(
                    "fvv",
                    value=st.session_state.fvv_val,
                    help="Google Form version flag. Usually `1`.",
                )
                st.session_state.fvv_val = fvv
                current_fvv = fvv
            with fm_c2:
                page_history: str = st.text_input(
                    "pageHistory",
                    value=st.session_state.ph_val,
                    help="Comma-separated page indices visited. Example: `0,1,2,3`.",
                )
                st.session_state.ph_val = page_history
                current_ph = page_history

        # ── Request Delay ─────────────────────────────────────────
        with st.expander("Request Delay", expanded=False):
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                min_delay: float = st.number_input(
                    "Min (sec)",
                    min_value=0.0,
                    max_value=60.0,
                    value=1.0,
                    step=0.5,
                    format="%.1f",
                )
            with d_col2:
                max_delay: float = st.number_input(
                    "Max (sec)",
                    min_value=0.0,
                    max_value=120.0,
                    value=3.0,
                    step=0.5,
                    format="%.1f",
                )
            if min_delay > max_delay:
                st.warning("⚠️ Min delay is greater than Max delay")

        opt1, opt2, opt3 = st.columns(3)
        with opt1:
            dry_run = st.checkbox(
                "Dry Run — build payload without sending",
                value=False,
                help="Test your mapping without actually submitting data to Google Forms.",
            )
        with opt2:
            shuffle_rows = st.checkbox(
                "Randomise row order",
                value=False,
                help="Submit rows in a random order.",
            )
        with opt3:
            include_sentinels: bool = st.checkbox(
                "Include Sentinel Fields",
                value=st.session_state.include_sentinels_val,
                help="Append `entry.XXX_sentinel = ''` for entries marked as sentinel.",
            )
            st.session_state.include_sentinels_val = include_sentinels

        st.write("")

        # ── Control buttons ───────────────────────────────────
        _sh("Controls")
        btn1, btn2, btn3 = st.columns([2, 2, 3])
        with btn1:
            start_btn = st.button(
                "Start Injection",
                disabled=st.session_state.is_running,
                use_container_width=True,
                type="primary",
            )
        with btn2:
            stop_btn = st.button(
                "Stop",
                disabled=not st.session_state.is_running,
                use_container_width=True,
            )
        with btn3:
            reset_btn = st.button(
                "Reset Log & Results",
                use_container_width=True,
            )

        if stop_btn:
            st.session_state.stop_flag[0] = True
            st.warning(
                "Stop signal sent. The process will halt after the current row.",
                icon="⏹️",
            )

        if reset_btn:
            st.session_state.results = []
            st.session_state.log_lines = []
            st.session_state.is_running = False
            st.session_state.stop_flag = [False]
            st.session_state.show_payload_preview = False
            st.success("Log and results have been reset.", icon="✅")
            st.rerun()

        # ── Injection runner ──────────────────────────────────
        if start_btn and not st.session_state.is_running:
            final_issues = validate_mappings(
                st.session_state.mappings, st.session_state.csv_columns
            )
            blocking = [
                iss
                for iss in final_issues
                if any(
                    kw in iss["issue"].lower()
                    for kw in (
                        "empty",
                        "invalid",
                        "not found",
                        "duplicate",
                        "kosong",
                        "tidak valid",
                        "tidak ditemukan",
                        "duplikasi",
                    )
                )
            ]

            if blocking:
                st.error(
                    "Fix the following mapping errors before proceeding:\n\n"
                    + "\n".join(
                        f"- **{b['entry_id']}**: {b['issue']}" for b in blocking
                    )
                )
            else:
                st.session_state.is_running = True
                st.session_state.stop_flag = [False]
                st.session_state.results = []
                st.session_state.log_lines = []

                _all_records = dataframe_to_records(
                    st.session_state.df.iloc[int(start_row) : int(end_row)]
                )
                if shuffle_rows:
                    random.shuffle(_all_records)

                total_recs = len(_all_records)

                _sh("⏳ Progress")
                progress_bar = st.progress(0, text="Starting…")
                status_empty = st.empty()
                _sh("📋 Live Log")
                log_empty = st.empty()

                _live_log: list[str] = []

                def _append_log(msg: str) -> None:
                    _live_log.append(msg)
                    st.session_state.log_lines = _live_log.copy()
                    html_lines = "<br>".join(
                        _colourise_log(ln) for ln in reversed(_live_log[-80:])
                    )
                    log_empty.markdown(
                        f"<div class='log-box'>{html_lines}</div>",
                        unsafe_allow_html=True,
                    )

                def _update_progress(current: int, total: int) -> None:
                    pct = current / total if total > 0 else 0
                    progress_bar.progress(
                        pct,
                        text=f"Row {current}/{total} ({pct * 100:.1f}%)",
                    )
                    status_empty.markdown(
                        f"**Running** — row **{current}** of **{total}**"
                    )

                _append_log(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Start "
                    f"{'DRY RUN' if dry_run else 'injection'} — "
                    f"{total_recs} rows | delay {min_delay}–{max_delay}s"
                )

                # ── Dry-run branch ───────────────────────────
                if dry_run:
                    _dry_results: list[dict] = []
                    for _idx, _row in enumerate(_all_records):
                        if st.session_state.stop_flag[0]:
                            _append_log(
                                f"[{datetime.now().strftime('%H:%M:%S')}] "
                                f"Stopped at row {_idx + 1}/{total_recs}"
                            )
                            break

                        _payload = build_payload(
                            row=_row,
                            mappings=st.session_state.mappings,
                            fvv=fvv,
                            page_history=page_history,
                            include_sentinels=include_sentinels,
                        )
                        _dry_results.append(
                            {
                                "success": True,
                                "status": 0,
                                "message": "DRY RUN — not submitted",
                                "ts": datetime.now().strftime("%H:%M:%S"),
                                "row_index": _idx,
                                "payload": _payload,
                            }
                        )
                        _append_log(
                            f"[{datetime.now().strftime('%H:%M:%S')}] "
                            f"Row {_idx + 1}/{total_recs} — "
                            f"payload built ({len(_payload)} fields)"
                        )
                        _update_progress(_idx + 1, total_recs)
                        time.sleep(0.03)

                    st.session_state.results = _dry_results

                # ── Live injection branch ────────────────────
                else:
                    _inj_results = run_bulk_submit(
                        form_url=form_url,
                        records=_all_records,
                        mappings=st.session_state.mappings,
                        fvv=fvv,
                        page_history=page_history,
                        include_sentinels=include_sentinels,
                        min_delay=min_delay,
                        max_delay=max_delay,
                        progress_callback=_update_progress,
                        log_callback=_append_log,
                        stop_flag=st.session_state.stop_flag,
                    )
                    st.session_state.results = _inj_results

                # ── Wrap-up ──────────────────────────────────
                st.session_state.is_running = False
                _summary_wrap = summarise_results(st.session_state.results)
                progress_bar.progress(1.0, text="Done ✅")
                status_empty.success(
                    f"Finished — "
                    f"**{_summary_wrap['success']}** succeeded / "
                    f"**{_summary_wrap['failed']}** failed / "
                    f"**{_summary_wrap['total']}** total",
                    icon="✅",
                )
                _append_log(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Done — "
                    f"{_summary_wrap['success']}/{_summary_wrap['total']} succeeded"
                )
                st.rerun()

    # ── Persisted log ─────────────────────────────────────────
    if not st.session_state.is_running and st.session_state.log_lines:
        _sh("📋 Submission Log")
        _render_log(st.session_state.log_lines)

    # ── Results ───────────────────────────────────────────────
    if st.session_state.results:
        _summary = summarise_results(st.session_state.results)

        _sh("Results Summary")
        rs1, rs2, rs3, rs4 = st.columns(4)
        rs1.metric("Total Submitted", f"{_summary['total']:,}")
        rs2.metric(
            "Succeeded",
            f"{_summary['success']:,}",
            delta=f"{_summary['rate'] * 100:.1f}%",
        )
        rs3.metric(
            "Failed",
            f"{_summary['failed']:,}",
            delta=(
                f"-{(1 - _summary['rate']) * 100:.1f}%"
                if _summary["failed"] > 0
                else None
            ),
            delta_color="inverse",
        )
        rs4.metric("Success Rate", f"{_summary['rate'] * 100:.1f}%")

        if _summary["total"] > 0:
            st.progress(
                _summary["rate"],
                text=f"Success rate: {_summary['rate'] * 100:.1f}%",
            )

        # ── Detail table ──────────────────────────────────────
        _sh("📄 Per-Row Results")
        _table_rows = []
        for _r in st.session_state.results:
            _table_rows.append(
                {
                    "Row": _r.get("row_index", 0) + 1,
                    "Status": "✅ Success" if _r.get("success") else "❌ Failed",
                    "HTTP Code": _r.get("status", "-"),
                    "Message": _r.get("message", ""),
                    "Time": _r.get("ts", ""),
                }
            )

        _results_df = pd.DataFrame(_table_rows)

        def _highlight_failed(row):
            if "Failed" in str(row.get("Status", "")):
                return ["background-color:#2d1b1b"] * len(row)
            return [""] * len(row)

        st.dataframe(
            _results_df.style.apply(_highlight_failed, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        # ── Export buttons ────────────────────────────────────
        _sh("Export Results")
        ex1, ex2, ex3 = st.columns(3)

        with ex1:
            st.download_button(
                "Download CSV",
                data=_results_df.to_csv(index=False).encode("utf-8"),
                file_name=f"injection_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with ex2:
            _json_export = json.dumps(
                [
                    {k: v for k, v in _r.items() if k != "payload"}
                    for _r in st.session_state.results
                ],
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
            st.download_button(
                "Download JSON",
                data=_json_export,
                file_name=f"injection_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

        with ex3:
            st.download_button(
                "Download Log (.txt)",
                data="\n".join(st.session_state.log_lines).encode("utf-8"),
                file_name=f"injection_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        # ── Failed payload inspector ──────────────────────────
        _failed_list = [_r for _r in st.session_state.results if not _r.get("success")]
        if _failed_list:
            with st.expander(
                f"🔍 Inspect Failed Payloads ({len(_failed_list)} items)",
                expanded=False,
            ):
                for _r in _failed_list[:15]:
                    _rnum = _r.get("row_index", 0) + 1
                    st.markdown(
                        f"**Row {_rnum}** — "
                        f"<span style='color:#f38ba8'>{_r.get('message', '')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.json(_r.get("payload", {}))
                    st.divider()
                if len(_failed_list) > 15:
                    st.caption(
                        f"… and {len(_failed_list) - 15} more failed payloads "
                        f"(see the results table above)."
                    )
