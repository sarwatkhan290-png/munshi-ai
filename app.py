import streamlit as st
import plotly.graph_objects as go

from dotenv import load_dotenv
load_dotenv()

from database import initialize_database, get_shop_users, get_shops, get_team_members, add_team_member
from services.auth_service import (
    authenticate_user,
    create_tenant_user,
    get_tenant_by_id,
    prepare_session_for_user,
    reset_session_for_logout,
)
from services.transaction_service import (
    process_transaction,
    get_customer_ledger,
    add_expense,
    add_sale,
    get_customer,
)
from services.analytics_service import (
    get_dashboard_summary,
    get_customer_balances,
    get_overdue_customers,
    get_udhaar_score,
    get_business_insights,
    get_sales_forecast,
    get_recent_transactions,
    get_top_debtors,
    get_transaction_history,
    get_expense_summary,
    get_monthly_business_data,
)
from services.qa_service import answer_business_question
from services.ocr_service import extract_transactions_from_image
from services.voice_service import transcribe_audio
from services.reminder_service import generate_reminder, generate_call_script, generate_whatsapp_link
from services.receipt_service import generate_receipt_text
from services.invoice_service import generate_invoice_pdf


# ============================================================
# DATABASE
# ============================================================

initialize_database()


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Munshi AI",
    page_icon="🤵",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if "theme_toggle" not in st.session_state:
    st.session_state.theme_toggle = True

if "user" not in st.session_state:
    st.session_state.user = None

if "tenant" not in st.session_state:
    st.session_state.tenant = None

if "active_page" not in st.session_state:
    st.session_state.active_page = "🏠 Dashboard"

if "nav_target" not in st.session_state:
    st.session_state.nav_target = None

if "app_mode" not in st.session_state:
    st.session_state.app_mode = "dashboard" if st.session_state.user is not None else "auth"


def current_tenant_id():
    """
    The single source of truth for "which shop's data am I allowed to see".

    Every data-access call in this file must go through this helper instead
    of hardcoding tenant_id=1 — that hardcoding was the root cause of the
    cross-tenant data leak fixed in this version. Raises instead of
    defaulting if somehow called before login, so a missing tenant fails
    loudly rather than silently falling back to shared data.
    """
    tenant = st.session_state.get("tenant")
    if not tenant or not tenant.get("id"):
        raise RuntimeError("current_tenant_id() called with no authenticated tenant in session")
    return tenant["id"]


def sync_theme_state():
    theme = st.session_state.get("theme", "dark")
    if theme not in ("dark", "light"):
        theme = "dark"
    st.session_state.theme = theme
    st.session_state.theme_toggle = theme == "dark"


def get_theme_css():
    theme = st.session_state.get("theme", "dark")
    if theme == "light":
        values = {
            "bg": "#f3f6fb",
            "bg_elevated": "#ffffff",
            "surface": "rgba(255, 255, 255, 0.9)",
            "text": "#0f172a",
            "muted": "#475569",
            "primary": "#0f766e",
            "primary_strong": "#115e59",
            "border": "rgba(15, 23, 42, 0.10)",
            "sidebar_bg": "linear-gradient(180deg, #f7f2ea 0%, #efe7da 100%)",
            "input_bg": "rgba(255, 255, 255, 0.78)",
            "table_head": "rgba(15, 92, 93, 0.04)",
            "button_secondary": "rgba(255, 255, 255, 0.7)",
            "status_bg": "rgba(15, 92, 93, 0.08)",
            "status_border": "rgba(15, 92, 93, 0.12)",
            "status_text": "#0a3f41",
            "badge_bg": "rgba(15, 92, 93, 0.09)",
            "badge_border": "rgba(15, 92, 93, 0.12)",
            "badge_text": "#0f5c5d",
            "chip_bg": "rgba(15, 92, 93, 0.08)",
            "chip_text": "#0a3f41",
            "card_bg": "rgba(255, 255, 255, 0.9)",
        }
    else:
        values = {
            "bg": "#0b1220",
            "bg_elevated": "#101a2b",
            "surface": "rgba(15, 23, 42, 0.9)",
            "text": "#edf4ff",
            "muted": "#a9b8cc",
            "primary": "#2bb4a3",
            "primary_strong": "#1e8d7d",
            "border": "rgba(148, 163, 184, 0.18)",
            "sidebar_bg": "linear-gradient(180deg, rgba(7, 12, 19, 0.98) 0%, rgba(15, 23, 42, 0.96) 100%)",
            "input_bg": "rgba(15, 23, 42, 0.75)",
            "table_head": "rgba(15, 23, 42, 0.95)",
            "button_secondary": "rgba(15, 23, 42, 0.7)",
            "status_bg": "rgba(52, 211, 153, 0.1)",
            "status_border": "rgba(52, 211, 153, 0.2)",
            "status_text": "#bff5d7",
            "badge_bg": "rgba(45, 212, 191, 0.12)",
            "badge_border": "rgba(45, 212, 191, 0.25)",
            "badge_text": "#99f6e4",
            "chip_bg": "rgba(43, 180, 163, 0.12)",
            "chip_text": "#9ef3e4",
            "card_bg": "rgba(15, 23, 42, 0.78)",
        }

    return """
    <style>
    :root {{
        --bg: {bg};
        --bg-elevated: {bg_elevated};
        --surface: {surface};
        --text: {text};
        --muted: {muted};
        --primary: {primary};
        --primary-strong: {primary_strong};
        --border: {border};
        --sidebar-bg: {sidebar_bg};
        --input-bg: {input_bg};
        --table-head: {table_head};
        --button-secondary: {button_secondary};
        --status-bg: {status_bg};
        --status-border: {status_border};
        --status-text: {status_text};
        --badge-bg: {badge_bg};
        --badge-border: {badge_border};
        --badge-text: {badge_text};
        --chip-bg: {chip_bg};
        --chip-text: {chip_text};
        --card-bg: {card_bg};
        --radius-sm: 12px;
        --radius-md: 18px;
        --radius-lg: 24px;
        --shadow-sm: 0 10px 24px rgba(15, 23, 42, 0.08);
        --shadow-md: 0 20px 48px rgba(15, 23, 42, 0.12);
    }}
    html, body, [data-testid="stAppViewContainer"], .stApp {{
        background: linear-gradient(180deg, {bg} 0%, {bg_elevated} 100%);
        color: var(--text);
    }}
    .block-container {{
        max-width: 1360px;
        padding-top: 1.25rem;
        padding-bottom: 2.5rem;
    }}
    .page-title {{
        font-size: clamp(2rem, 2.5vw, 2.9rem);
        line-height: 1.1;
        font-weight: 800;
        letter-spacing: -0.05em;
        margin: 0;
        color: var(--text);
    }}
    .page-subtitle {{
        color: var(--muted);
        font-size: 0.96rem;
        margin-top: 0.35rem;
    }}
    .status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.6rem 0.8rem;
        border-radius: 999px;
        background: var(--status-bg);
        border: 1px solid var(--status-border);
        color: var(--status-text);
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        white-space: nowrap;
    }}
    .metric-card, .quick-card, .insight-card, .step-card, .profile-card, .chat-panel, div[data-testid="stMetric"] {{
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-sm);
        padding: 1rem 1.1rem;
    }}
    .metric-label, .section-title, .sidebar-section {{
        color: var(--muted);
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }}
    .metric-value, .quick-title, .step-title, .insight-text {{
        color: var(--text);
    }}
    .ai-badge {{
        display: inline-block;
        background: var(--badge-bg);
        border: 1px solid var(--badge-border);
        border-radius: 999px;
        color: var(--badge-text);
        padding: 0.5rem 0.8rem;
        font-size: 0.7rem;
        font-weight: 800;
    }}
    .step-number {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: var(--chip-bg);
        color: var(--chip-text);
        font-weight: 800;
    }}
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, var(--primary), var(--primary-strong));
        border: 1px solid rgba(43, 180, 163, 0.25);
        color: white;
    }}
    .stButton > button[kind="secondary"] {{
        background: var(--button-secondary);
        border: 1px solid var(--border);
        color: var(--text);
    }}
    section[data-testid="stSidebar"] {{
        background: var(--sidebar-bg);
        border-right: 1px solid var(--border);
    }}
    section[data-testid="stSidebar"] * {{
        color: var(--text);
    }}
    .stTextArea textarea, .stTextInput input, .stNumberInput input, .stSelectbox select {{
        background: var(--input-bg);
        color: var(--text);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
    }}
    div[data-testid="stDataFrame"] th {{
        background: var(--table-head);
        color: var(--text);
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }}
    .stTabs [role="tab"][aria-selected="true"] {{
        background: rgba(43, 180, 163, 0.1);
        border: 1px solid rgba(43, 180, 163, 0.2);
    }}
    </style>
    """.format(**values)


sync_theme_state()
st.markdown(get_theme_css(), unsafe_allow_html=True)

if st.session_state.user is None:
    st.session_state.app_mode = "auth"
    st.title("Munshi AI SaaS")
    st.caption("One workspace for your team, your shops, and your sales data.")

    tab_login, tab_register = st.tabs(["Login", "Create account"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", use_container_width=True, type="primary"):
            result = authenticate_user(email, password)
            if result["success"]:
                st.session_state.user = result["user"]
                st.session_state.tenant = get_tenant_by_id(result["user"]["tenant_id"])
                prepare_session_for_user(st.session_state)
                st.session_state.app_mode = "dashboard"
                st.rerun()
            else:
                st.error(result["message"])

    with tab_register:
        company_name = st.text_input("Business name")
        full_name = st.text_input("Your name")
        new_email = st.text_input("Work email", key="register_email")
        new_password = st.text_input("Password", type="password", key="register_password")

        if st.button("Create account", use_container_width=True):
            if not company_name.strip() or not full_name.strip() or not new_email.strip() or not new_password.strip():
                st.warning("Please fill in all fields.")
            else:
                result = create_tenant_user(
                    name=full_name,
                    email=new_email,
                    password=new_password,
                    tenant_name=company_name,
                    role="owner",
                )
                if result["success"]:
                    st.session_state.user = result["user"]
                    st.session_state.tenant = get_tenant_by_id(result["user"]["tenant_id"])
                    prepare_session_for_user(st.session_state)
                    st.session_state.app_mode = "dashboard"
                    st.success("Account created successfully. Welcome to Munshi AI SaaS.")
                    st.rerun()
                else:
                    st.error(result["message"])

    st.stop()

st.session_state.app_mode = "dashboard" if st.session_state.user is not None else "auth"

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div class="sidebar-brand">Munshi AI</div>
        <div class="sidebar-subtitle">AI business desk for daily trade</div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.user:
        st.markdown(
            f"""
            <div class="profile-card">
                <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); margin-bottom: 0.35rem;">Workspace</div>
                <div style="font-size: 1.05rem; font-weight: 800; margin-bottom: 0.2rem;">{st.session_state.user['name']}</div>
                <div style="font-size: 0.82rem; color: var(--muted);">{st.session_state.tenant['name'] if st.session_state.tenant else 'Shop workspace'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Logout", use_container_width=True, type="secondary"):
            reset_session_for_logout(st.session_state)
            st.rerun()

    nav_pages = [
        "🏠 Dashboard",
        "Analytics",
        "💬 Ask Munshi",
        "📷 Scan Khata",
        "🎙️ Voice Munshi",
        "📒 Customers",
        "⚠️ Overdue & Scores",
        "💰 Transactions",
        "💸 Expenses",
        "📊 Reports",
        "💳 Billing",
        "👥 Team",
    ]

    grouped_pages = {
        "Overview": ["🏠 Dashboard", "Analytics"],
        "Money": ["💰 Transactions", "💸 Expenses", "📊 Reports", "💳 Billing"],
        "Customers": ["📒 Customers", "⚠️ Overdue & Scores"],
        "AI Tools": ["💬 Ask Munshi", "📷 Scan Khata", "🎙️ Voice Munshi"],
        "Account": ["👥 Team"],
    }

    selected_page = st.session_state.nav_target or st.session_state.active_page
    if selected_page not in nav_pages:
        selected_page = "🏠 Dashboard"

    st.markdown('<div class="sidebar-section">Navigation</div>', unsafe_allow_html=True)
    for section_name, pages in grouped_pages.items():
        st.markdown(f'<div class="sidebar-section">{section_name}</div>', unsafe_allow_html=True)
        for label in pages:
            is_active = label == selected_page
            if st.button(
                label,
                key=f"nav_{label}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.active_page = label
                st.session_state.nav_target = label
                st.rerun()

    st.markdown('<div class="sidebar-section">Settings</div>', unsafe_allow_html=True)
    theme_choice = st.radio(
        "Theme",
        ["Light", "Dark"],
        index=0 if st.session_state.get("theme", "dark") == "light" else 1,
        horizontal=True,
        key="theme_choice",
    )
    selected_theme = "light" if theme_choice == "Light" else "dark"
    if st.session_state.get("theme") != selected_theme:
        st.session_state.theme = selected_theme
        sync_theme_state()

    shops = get_shops(current_tenant_id())
    if shops:
        st.caption("Active workspace")
        for shop_id, shop_name, owner_name, phone, address in shops:
            st.caption(f"• {shop_name}")

    users = get_shop_users(current_tenant_id())
    if users:
        st.caption("Team")
        for user_id, name, role, phone in users:
            st.caption(f"• {name} · {role}")

    st.caption("Local database connected")
    st.caption("Business data stays on this device")

page = st.session_state.nav_target or st.session_state.active_page or "🏠 Dashboard"
st.session_state.active_page = page
st.session_state.nav_target = None

# ============================================================
# HELPERS
# ============================================================


def money(value):
    return f"Rs. {float(value or 0):,.0f}"


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    summary = get_dashboard_summary(current_tenant_id())
    recent_activity = get_recent_transactions(current_tenant_id(), 5)
    top_debtors = get_top_debtors(current_tenant_id(), 3)
    overdue = get_overdue_customers(current_tenant_id())

    st.markdown(
        """
        <div class="page-header">
            <div>
                <div class="page-title">Good evening 👋</div>
                <div class="page-subtitle">Your business is moving, and Munshi is helping you stay ahead.</div>
            </div>
            <div class="status-pill">● Munshi ready</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="workspace-banner">
            <div>
                <div class="ai-badge">AI business assistant</div>
                <div class="ai-title">Your modern business cockpit.</div>
                <div class="ai-description">
                    Turn daily sales, payments, notes, and customer follow-ups into a single clear view.
                    Munshi helps you track cash flow, prioritize collections, and act faster with less admin work.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="margin-top: 1rem;">
        """,
        unsafe_allow_html=True,
    )
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown('<div class="metric-card"><span class="metric-label">Sales</span><span class="metric-value">{}</span></div>'.format(money(summary['sales'])), unsafe_allow_html=True)
    with k2:
        st.markdown('<div class="metric-card"><span class="metric-label">Collected</span><span class="metric-value">{}</span></div>'.format(money(summary['paid'])), unsafe_allow_html=True)
    with k3:
        st.markdown('<div class="metric-card"><span class="metric-label">Outstanding</span><span class="metric-value">{}</span></div>'.format(money(summary['due'])), unsafe_allow_html=True)
    with k4:
        st.markdown('<div class="metric-card"><span class="metric-label">Expenses</span><span class="metric-value">{}</span></div>'.format(money(summary['expenses'])), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Quick business capture</div>', unsafe_allow_html=True)
    transaction_text = st.text_area(
        "Enter a transaction",
        placeholder="Example: Ali ne 25 hazar ka maal liya aur 10 hazar diye...",
        height=120,
        label_visibility="collapsed",
    )

    quick_capture_col, audio_col = st.columns([4, 1])
    with quick_capture_col:
        if st.button("🤖 Process with Munshi", type="primary", use_container_width=True):
            if not transaction_text.strip():
                st.warning("Tell Munshi what happened first.")
            else:
                result = process_transaction(current_tenant_id(), transaction_text)
                if result["success"]:
                    st.success(f"Done. {result['customer']}'s record has been saved.")
                    source_badge = (
                        "🧠 AI-powered extraction"
                        if result.get("source") == "llm"
                        else "📐 Pattern-based extraction"
                    )
                    st.caption(source_badge)

                    a, b, c = st.columns(3)
                    with a:
                        st.metric("Sale", f"Rs. {result['amount']:,.0f}")
                    with b:
                        st.metric("Paid", f"Rs. {result['paid']:,.0f}")
                    with c:
                        st.metric("Outstanding", f"Rs. {result['due']:,.0f}")

                    receipt_text = generate_receipt_text(
                        customer_name=result["customer"],
                        amount=result["amount"],
                        paid=result["paid"],
                        due=result["due"],
                    )
                    with st.expander("🧾 View and download receipt"):
                        st.code(receipt_text, language=None)
                        st.download_button(
                            "⬇️ Download receipt",
                            data=receipt_text,
                            file_name=f"receipt_{result['customer']}.txt",
                            mime="text/plain",
                        )
                else:
                    st.error(result["message"])
    with audio_col:
        if st.button("🎙️ Voice", use_container_width=True):
            st.session_state.nav_target = "🎙️ Voice Munshi"
            st.rerun()

    action_icons = [
        ("💬", "Ask Munshi", "Turn notes into records"),
        ("📷", "Scan Khata", "Parse notebooks and paper slips"),
        ("🎙️", "Voice Munshi", "Log transactions by voice"),
        ("📊", "Reports", "Grow with clearer trends"),
    ]

    action_cols = st.columns(4)
    for col, (icon, title, desc) in zip(action_cols, action_icons):
        with col:
            st.markdown(
                f"""
                <div class="quick-card">
                    <div class="quick-icon">{icon}</div>
                    <div class="quick-title">{title}</div>
                    <div class="quick-description">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-title">Business pulse</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total sales", money(summary['sales']))
    with k2:
        st.metric("Collected", money(summary['paid']))
    with k3:
        st.metric("Outstanding", money(summary['due']))
    with k4:
        st.metric("Expenses", money(summary['expenses']))

    st.markdown('<div class="section-title">Financial health</div>', unsafe_allow_html=True)
    p1, p2 = st.columns([2, 1])
    with p1:
        st.metric("Estimated profit", f"Rs. {summary['profit']:,.0f}")
    with p2:
        margin = (summary['profit'] / summary['sales'] * 100) if summary['sales'] > 0 else 0
        st.metric("Profit margin", f"{margin:.1f}%")

    insight_col1, insight_col2 = st.columns(2)

    with insight_col1:
        st.markdown('<div class="section-title">Top debtors</div>', unsafe_allow_html=True)
        if not top_debtors:
            st.info("No outstanding balances right now.")
        else:
            for _, name, _, _, due, _ in top_debtors:
                st.markdown(
                    f"<div class='quick-card'><div class='quick-title'>{name}</div><div class='quick-description'>Outstanding: Rs. {due:,.0f}</div></div>",
                    unsafe_allow_html=True,
                )

    with insight_col2:
        st.markdown('<div class="section-title">Recent activity</div>', unsafe_allow_html=True)
        if not recent_activity:
            st.info("No transactions recorded yet.")
        else:
            for customer, tx_type, description, amount, paid, due, date in recent_activity:
                st.markdown(
                    f"""
                    <div class="quick-card">
                        <div class="quick-title">{customer}</div>
                        <div class="quick-description">{tx_type.upper()} · {description or 'No description'}</div>
                        <div class="quick-description">Rs. {amount:,.0f} · Paid {paid:,.0f} · Due {due:,.0f}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown('<div class="section-title">Munshi insight</div>', unsafe_allow_html=True)
    insights = get_business_insights(current_tenant_id())
    for insight_text in insights:
        st.markdown(
            """
            <div class="insight-card">
                <div class="insight-label">AI insight</div>
                <div class="insight-text">{}</div>
            </div>
            """.format(insight_text),
            unsafe_allow_html=True,
        )

    if overdue:
        st.markdown('<div class="section-title">Recommended actions</div>', unsafe_allow_html=True)
        for row in overdue[:3]:
            st.info(f"Follow up with {row['name']} for Rs. {row['due']:,.0f} — {row['days_overdue']} days overdue.")

    st.markdown('<div class="section-title">Quick actions</div>', unsafe_allow_html=True)
    q1, q2, q3, q4 = st.columns(4)
    quick_actions = [
        ("➕", "Record Sale", "Add a sale", "🏠 Dashboard"),
        ("💵", "Record Payment", "Track received money", "🏠 Dashboard"),
        ("💸", "Add Expense", "Log a new cost", "💸 Expenses"),
        ("👤", "Customer Ledger", "Check balances", "📒 Customers"),
    ]
    for column, (icon, title, description, destination) in zip([q1, q2, q3, q4], quick_actions):
        with column:
            if st.button(f"{icon} {title}", key=f"quick_{title}", use_container_width=True):
                st.session_state.nav_target = destination
                st.rerun()
            st.caption(description)


# ============================================================
# ANALYTICS
# ============================================================

elif page == "Analytics":

    st.title("📈 Analytics")
    st.write("Enterprise-level customer and revenue analytics for faster decision making.")

    monthly_data = get_monthly_business_data(current_tenant_id(), 12)
    balances = get_customer_balances(current_tenant_id())

    if monthly_data:
        chart_df = [
            {"Month": row[0], "Sales": float(row[1]), "Collected": float(row[2]), "Outstanding": float(row[3])}
            for row in monthly_data
        ]
        st.markdown('<div class="section-title">Revenue trend</div>', unsafe_allow_html=True)
        st.line_chart(chart_df, x="Month", y=["Sales", "Collected", "Outstanding"])

    if balances:
        customer_chart = [
            {"Customer": name, "Outstanding": float(due), "Paid": float(paid)}
            for _, name, _, paid, due, _ in balances[:8]
        ]
        st.markdown('<div class="section-title">Customer balance mix</div>', unsafe_allow_html=True)
        st.bar_chart(customer_chart, x="Customer", y=["Outstanding", "Paid"])

    top_customers = balances[:5]
    if top_customers:
        st.markdown('<div class="section-title">Top customer accounts</div>', unsafe_allow_html=True)
        rows = [
            {"Customer": name, "Credit": float(credit), "Paid": float(paid), "Due": float(due)}
            for _, name, credit, paid, due, _ in top_customers
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)


# ============================================================
# ASK MUNSHI
# ============================================================

elif page == "💬 Ask Munshi":

    st.title("💬 Ask Munshi")
    st.write("Ask natural-language questions about your sales, payments, cash flow, and business trends.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    example_prompts = [
        "Mera total sale kitna hai?",
        "Kitna paisa customers se lena hai?",
        "Mera profit kitna hua?",
        "Kon se customer sab se zyada overdue hain?",
    ]

    st.caption("Try one of these examples:")
    example_cols = st.columns(2)
    for idx, prompt in enumerate(example_prompts):
        with example_cols[idx % 2]:
            if st.button(prompt, key=f"prompt_{idx}", use_container_width=True):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.spinner("Munshi is analyzing your business data..."):
                    answer = answer_business_question(current_tenant_id(), prompt)
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
                st.rerun()

    st.markdown('<div class="chat-panel">', unsafe_allow_html=True)
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask Munshi about your business...")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.spinner("Munshi is analyzing your business data..."):
            answer = answer_business_question(current_tenant_id(), prompt)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# SCAN KHATA
# ============================================================

elif page == "📷 Scan Khata":

    st.title("📷 Scan Khata")
    st.write("Upload a photo of a handwritten khata page. Munshi will read it and draft transactions for you to review before saving.")

    step_cols = st.columns(3)
    steps = [
        ("1", "Upload", "Add your khata image"),
        ("2", "Process", "Munshi reads the page"),
        ("3", "Review", "Confirm before saving"),
    ]
    for col, (num, label, desc) in zip(step_cols, steps):
        with col:
            st.markdown(f"""
            <div class="step-card">
                <div class="step-number">{num}</div>
                <div class="step-label">{label}</div>
                <div class="step-title">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    uploaded_image = st.file_uploader("Khata photo", type=["jpg", "jpeg", "png"], help="JPG, JPEG, or PNG up to your system limit.")

    if uploaded_image is not None:
        st.image(uploaded_image, caption="Uploaded khata page", width=350)

        if st.button("🔍 Extract transactions", type="primary"):
            with st.spinner("Munshi is reading the khata page and extracting customer entries..."):
                drafts = extract_transactions_from_image(
                    uploaded_image.getvalue(),
                    mime_type=uploaded_image.type or "image/jpeg",
                )

            if drafts is None:
                st.error("OCR is not configured yet. Add OPENAI_API_KEY to your .env file and retry. This is required for khata scanning.")
            elif not drafts:
                st.warning("No readable transactions were found in this photo. Try a clearer image, better lighting, or a cropped page.")
            else:
                st.session_state["khata_drafts"] = drafts
                st.success("Draft transactions found. Review and confirm below.")

    if st.session_state.get("khata_drafts"):
        st.markdown('<div class="section-title">Review before saving</div>', unsafe_allow_html=True)
        edited = st.data_editor(
            st.session_state["khata_drafts"],
            column_config={
                "customer": "Customer",
                "amount": st.column_config.NumberColumn("Amount (Rs.)"),
                "type": st.column_config.SelectboxColumn("Type", options=["sale", "payment"]),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="khata_editor",
        )

        if st.button("✅ Confirm & save all", type="primary"):
            saved = 0
            for row in edited:
                if not row.get("customer") or not row.get("amount"):
                    continue

                if row["type"] == "sale":
                    add_sale(
                        current_tenant_id(),
                        customer_name=row["customer"],
                        amount=float(row["amount"]),
                        paid=0,
                        description="Imported from khata scan",
                    )
                else:
                    from services.transaction_service import add_payment
                    add_payment(current_tenant_id(), row["customer"], float(row["amount"]))

                saved += 1

            st.success(f"Saved {saved} transaction(s) to the ledger.")
            st.session_state["khata_drafts"] = None


# ============================================================
# VOICE MUNSHI
# ============================================================

elif page == "🎙️ Voice Munshi":

    st.title("🎙️ Voice Munshi")
    st.write("Upload a short voice note (Urdu, Roman Urdu, or English) describing a transaction, and Munshi will transcribe and record it.")

    step_cols = st.columns(3)
    steps = [
        ("1", "Upload", "Add your voice note"),
        ("2", "Listen", "Munshi transcribes"),
        ("3", "Record", "Save the transaction"),
    ]
    for col, (num, label, desc) in zip(step_cols, steps):
        with col:
            st.markdown(f"""
            <div class="step-card">
                <div class="step-number">{num}</div>
                <div class="step-label">{label}</div>
                <div class="step-title">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    uploaded_audio = st.file_uploader("Voice note", type=["wav", "mp3", "m4a", "ogg"], help="Audio notes recorded in Urdu, Roman Urdu, or English.")

    if uploaded_audio is not None:
        st.audio(uploaded_audio)

        if st.button("🎧 Transcribe & process", type="primary"):
            with st.spinner("Munshi is listening carefully and turning your note into a transaction..."):
                transcript = transcribe_audio(uploaded_audio)

            if transcript is None:
                st.error("Voice transcription needs a configured OpenAI API key and internet access. Add OPENAI_API_KEY to your .env file and try again.")
            else:
                st.info(f'Munshi heard: "{transcript}"')
                result = process_transaction(current_tenant_id(), transcript)

                if result["success"]:
                    st.success(f"Done. {result['customer']}'s transaction has been recorded.")
                else:
                    st.error(result["message"])


# ============================================================
# CUSTOMERS
# ============================================================

elif page == "📒 Customers":

    st.title("📒 Customers")

    st.write(
        "View all customer balances, or look up a single customer's "
        "full ledger."
    )

    balances = get_customer_balances(current_tenant_id())

    if balances:

        st.markdown(
            '<div class="section-title">All Customers</div>',
            unsafe_allow_html=True,
        )

        st.dataframe(
            [
                {
                    "Customer": name,
                    "Total Credit (Rs.)": f"{credit:,.0f}",
                    "Total Paid (Rs.)": f"{paid:,.0f}",
                    "Outstanding (Rs.)": f"{due:,.0f}",
                }
                for (_, name, credit, paid, due, _) in balances
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(
        '<div class="section-title">Customer Detail</div>',
        unsafe_allow_html=True,
    )

    customer_name = st.text_input(
        "Customer name",
        placeholder="Example: Ahmed",
    )

    if st.button(
        "View Customer",
        type="primary",
    ):

        if not customer_name.strip():

            st.warning("Enter a customer name.")

        else:

            ledger = get_customer_ledger(current_tenant_id(), customer_name)

            if not ledger:

                st.info(
                    f"No transactions found for {customer_name}."
                )

            else:

                customer_record = get_customer(current_tenant_id(), customer_name)

                if customer_record:

                    score = get_udhaar_score(current_tenant_id(), customer_record[0])
                    total_credit = sum(float(item[3]) for item in ledger)
                    total_paid = sum(float(item[4]) for item in ledger)
                    total_due = sum(float(item[5]) for item in ledger)

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Total Credit", f"Rs. {total_credit:,.0f}")
                    with c2:
                        st.metric("Total Paid", f"Rs. {total_paid:,.0f}")
                    with c3:
                        st.metric("Outstanding", f"Rs. {total_due:,.0f}")

                    if score["score"] is not None:
                        s1, s2 = st.columns(2)
                        with s1:
                            st.metric("Udhaar Reliability Score", f"{score['score']} / 100")
                        with s2:
                            st.metric("Risk Level", score["risk_level"])

                        st.caption(
                            "An internal indicator based on this shop's own transaction history — not a formal credit score."
                        )

                st.success(
                    f"{len(ledger)} transaction(s) found."
                )

                invoice_items = [
                    {
                        "description": description or transaction_type,
                        "amount": float(amount),
                        "paid": float(paid),
                        "due": float(due),
                    }
                    for _, transaction_type, description, amount, paid, due, _ in ledger
                ]
                pdf_bytes = generate_invoice_pdf(customer_name, invoice_items)
                st.download_button(
                    "⬇️ Download Invoice PDF",
                    data=pdf_bytes,
                    file_name=f"invoice_{customer_name.lower().replace(' ', '_')}.pdf",
                    mime="application/pdf",
                )

                for transaction in ledger:

                    (
                        transaction_id,
                        transaction_type,
                        description,
                        amount,
                        paid,
                        due,
                        date,
                    ) = transaction

                    with st.container():

                        st.markdown(
                            f"""
                            **{transaction_type.upper()}**  
                            {description}
                            
                            Amount: **Rs. {amount:,.0f}**  
                            Paid: **Rs. {paid:,.0f}**  
                            Due: **Rs. {due:,.0f}**  
                            Date: {date}
                            """
                        )

                        st.divider()


# ============================================================
# OVERDUE & SCORES
# ============================================================

elif page == "⚠️ Overdue & Scores":

    st.title("⚠️ Overdue & Payment Priority")

    st.write(
        "Customers whose balance has been outstanding for 30+ days, "
        "ranked by how overdue they are."
    )

    overdue_customers = get_overdue_customers(current_tenant_id())

    if not overdue_customers:

        st.success("✅ No customers are currently overdue by 30+ days.")

    else:

        for row in overdue_customers:

            with st.container():

                c1, c2, c3 = st.columns([2, 1, 1])

                with c1:
                    st.markdown(f"**🔴 {row['name']}**")
                    st.caption(f"{row['days_overdue']} days overdue")

                with c2:
                    st.metric("Due", f"Rs. {row['due']:,.0f}")

                with c3:

                    if st.button(
                        "🔔 Reminder",
                        key=f"reminder_{row['customer_id']}",
                    ):
                        st.session_state[f"reminder_text_{row['customer_id']}"] = (
                            generate_reminder(row["name"], row["due"])
                        )

                    if st.button(
                        "📞 Call Script",
                        key=f"call_{row['customer_id']}",
                    ):
                        st.session_state[f"call_text_{row['customer_id']}"] = (
                            generate_call_script(
                                row["name"], row["due"], row["days_overdue"]
                            )
                        )

                if st.session_state.get(f"reminder_text_{row['customer_id']}"):
                    reminder_text = st.session_state[f"reminder_text_{row['customer_id']}" ]
                    st.text_area(
                        "Reminder message",
                        reminder_text,
                        key=f"reminder_area_{row['customer_id']}",
                    )
                    whatsapp_link = generate_whatsapp_link(reminder_text)
                    st.link_button("📲 Send on WhatsApp", whatsapp_link)

                if st.session_state.get(f"call_text_{row['customer_id']}"):
                    st.text_area(
                        "Call script",
                        st.session_state[f"call_text_{row['customer_id']}"],
                        key=f"call_area_{row['customer_id']}",
                    )

                st.divider()


# ============================================================
# BILLING
# ============================================================

elif page == "💳 Billing":

    st.title("💳 Billing & subscriptions")
    st.write("Modern subscription management and plan visibility for your business workspace.")

    plan_cards = [
        ("Starter", "Rs. 0", "Perfect for solo businesses", ["Basic dashboard", "Up to 3 team members", "Standard reporting"]),
        ("Growth", "Rs. 3,500", "Best for growing teams", ["Advanced analytics", "AI transaction capture", "Priority support"]),
        ("Enterprise", "Rs. 9,500", "For larger operations", ["Multi-user admin", "Custom invoice branding", "Dedicated onboarding"]),
    ]

    cols = st.columns(3)
    for col, (plan, price, subtext, features) in zip(cols, plan_cards):
        with col:
            st.markdown(
                f"""
                <div class="pricing-card">
                    <div class="ai-badge">{plan}</div>
                    <div class="ai-title" style="font-size: 2rem; margin: 0 0 10px;">{price}</div>
                    <div class="quick-description" style="color: #94a3b8; margin-bottom: 20px;">{subtext}</div>
                    <ul style="padding-left: 18px; color: #e2e8f0; line-height: 2;">
                        {''.join(f'<li>{feature}</li>' for feature in features)}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(f"Choose {plan}", key=f"plan_{plan}", use_container_width=True)

    st.markdown('<div class="section-title">Current workspace status</div>', unsafe_allow_html=True)
    usage_col1, usage_col2, usage_col3 = st.columns(3)
    with usage_col1:
        st.metric("Current plan", "Growth")
    with usage_col2:
        st.metric("Seats used", "3 / 10")
    with usage_col3:
        st.metric("Billing status", "Active")


# ============================================================
# TEAM
# ============================================================

elif page == "👥 Team":

    st.title("👥 Team & admin")
    st.write("Manage your organization, staff roles, and access for the workspace.")

    members = get_team_members(current_tenant_id())
    if members:
        st.markdown('<div class="section-title">Team directory</div>', unsafe_allow_html=True)
        team_data = [
            {"Name": name, "Role": role, "Phone": phone or "-"}
            for _, name, role, phone in members
        ]
        st.dataframe(team_data, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Add staff member</div>', unsafe_allow_html=True)
    with st.form("add_team_member"):
        member_name = st.text_input("Full name")
        member_role = st.selectbox("Role", ["Owner", "Manager", "Staff", "Accountant"])
        member_phone = st.text_input("Phone")
        submitted = st.form_submit_button("Add member")

    if submitted:
        if not member_name.strip():
            st.warning("Please enter a member name.")
        else:
            add_team_member(current_tenant_id(), member_name, member_role, member_phone)
            st.success(f"{member_name} was added to the team.")
            st.rerun()


# ============================================================
# TRANSACTIONS
# ============================================================

elif page == "💰 Transactions":

    st.title("💰 Transactions")

    summary = get_dashboard_summary(current_tenant_id())
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Sales", money(summary["sales"]))
    with c2:
        st.metric("Collected", money(summary["paid"]))
    with c3:
        st.metric("Outstanding", money(summary["due"]))
    with c4:
        st.metric("Transactions", len(get_transaction_history(current_tenant_id(), limit=500)))

    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        customer_filter = st.text_input("Search customer", placeholder="Type customer name")
    with filter_col2:
        tx_type = st.selectbox("Type", ["all", "sale", "payment"])

    history = get_transaction_history(current_tenant_id(), limit=500, customer_name=customer_filter, transaction_type=tx_type)

    if not history:
        st.info("No transaction entries match the current filter.")
    else:
        st.dataframe(
            [
                {
                    "Customer": customer,
                    "Type": transaction_type,
                    "Description": description or "-",
                    "Amount": float(amount),
                    "Paid": float(paid),
                    "Due": float(due),
                    "Date": date,
                }
                for customer, transaction_type, description, amount, paid, due, date in history
            ],
            use_container_width=True,
            hide_index=True,
        )

        csv_data = "Customer,Type,Description,Amount,Paid,Due,Date\n" + "\n".join(
            [
                f"{customer},{transaction_type},{description or '-'} ,{amount},{paid},{due},{date}"
                for customer, transaction_type, description, amount, paid, due, date in history
            ]
        )
        st.download_button(
            "⬇️ Download CSV",
            data=csv_data,
            file_name="transactions.csv",
            mime="text/csv",
        )


# ============================================================
# EXPENSES
# ============================================================

elif page == "💸 Expenses":

    st.title("💸 Expenses")

    summary = get_dashboard_summary(current_tenant_id())
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Expenses", money(summary["expenses"]))
    with c2:
        st.metric("Estimated Profit", money(summary["profit"]))
    with c3:
        st.metric("Expense Categories", len(get_expense_summary(current_tenant_id())))

    expense_cols = st.columns([1.2, 1])
    with expense_cols[0]:
        category = st.selectbox(
            "Category",
            [
                "Electricity",
                "Rent",
                "Transport",
                "Salary",
                "Inventory",
                "Internet",
                "Maintenance",
                "Other",
            ],
        )

        amount = st.number_input("Amount (Rs.)", min_value=0.0, step=100.0)
        description = st.text_input("Description", placeholder="Example: Shop electricity bill")

        if st.button("💾 Save Expense", type="primary"):
            if amount <= 0:
                st.warning("Enter a valid amount.")
            else:
                result = add_expense(current_tenant_id(), category=category, amount=amount, description=description)
                st.success(f"Expense recorded: Rs. {result['amount']:,.0f}")
                st.rerun()

    with expense_cols[1]:
        st.markdown('<div class="section-title">Expense Breakdown</div>', unsafe_allow_html=True)
        expense_rows = get_expense_summary(current_tenant_id())
        if not expense_rows:
            st.info("No expenses logged yet.")
        else:
            chart_data = [{"Category": category, "Amount": float(total)} for category, total in expense_rows]
            st.bar_chart(chart_data, x="Category", y="Amount")

            for category_name, total in expense_rows:
                st.caption(f"{category_name}: {money(total)}")


# ============================================================
# REPORTS
# ============================================================

elif page == "📊 Reports":

    st.title("📊 Reports")

    summary = get_dashboard_summary(current_tenant_id())
    monthly_data = get_monthly_business_data(current_tenant_id(), 12)
    expense_rows = get_expense_summary(current_tenant_id())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Sales", money(summary['sales']))
    with c2:
        st.metric("Collected", money(summary['paid']))
    with c3:
        st.metric("Outstanding", money(summary['due']))
    with c4:
        st.metric("Profit", money(summary['profit']))

    if monthly_data:
        chart_df = [
            {
                "Month": row[0],
                "Sales": float(row[1]),
                "Collected": float(row[2]),
                "Outstanding": float(row[3]),
            }
            for row in monthly_data
        ]

        st.markdown('<div class="section-title">📈 Monthly Business Trend</div>', unsafe_allow_html=True)
        st.line_chart(chart_df, x="Month", y=["Sales", "Collected", "Outstanding"])

    st.markdown('<div class="section-title">🧾 Sales Forecast</div>', unsafe_allow_html=True)
    forecast = get_sales_forecast(current_tenant_id())
    if forecast is None:
        st.info("Munshi needs at least two months of sales history to estimate a trend.")
    else:
        st.metric("Estimated Next Month's Sales", f"Rs. {forecast['forecast']:,.0f}")
        st.caption("A simple trend-based estimate from your sales history — not a guaranteed forecast.")
        forecast_chart = [{"Month": month, "Sales": sales} for month, sales in forecast["history"]]
        st.line_chart(forecast_chart, x="Month", y="Sales")

    st.markdown('<div class="section-title">💸 Expense Mix</div>', unsafe_allow_html=True)
    if not expense_rows:
        st.info("No expense data yet. Add an expense to populate this report.")
    else:
        expense_chart = [{"Category": category, "Amount": float(total)} for category, total in expense_rows]
        st.bar_chart(expense_chart, x="Category", y="Amount")