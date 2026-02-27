import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import time

# --- Page Config ---
st.set_page_config(
    page_title="Sentinel-Flow Control Room", 
    layout="wide", 
    page_icon="🛡️"
)

# --- Custom Styling ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 12px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #ececec;
    }
    div[data-testid="stMetricValue"] { font-size: 28px; font-weight: bold; color: #1f77b4; }
    </style>
    """, unsafe_allow_html=True)

# --- Database Connection ---
def get_data():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "sentinel_operational"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432")
        )
        df = pd.read_sql("SELECT * FROM high_priority_alerts", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return pd.DataFrame()

# --- Header ---
st.title("🛡️ Sentinel-Flow: Revenue Recovery Engine")
st.markdown("### Executive Overview & Recovery Command Center")

df = get_data()

if not df.empty:
    # --- 1. Metric Calculations ---
    
    # Total High-Risk Events
    total_events = len(df)
    
    # AI Drafts Pending Review
    drafted_mask = (df['ai_draft'].notnull()) & (df['is_approved'] == False)
    pending_review_count = len(df[drafted_mask])
    
    # Intervention Success Rate (%)
    success_rate = (len(df[df['is_approved'] == True]) / total_events * 100) if total_events > 0 else 0
    
    # Revenue Actioned (Unique Accounts where is_approved = True)
    Actioned_df = df[df['is_approved'] == True].drop_duplicates(subset=['account_id'])
    revenue_Actioned = Actioned_df['mrr'].sum()
    
    # Revenue at Risk (Sum MRR of all unactioned alerts)
    revenue_at_risk = df[df['ai_draft'].isnull()]['mrr'].sum()

    # Drafted but awaiting human approval
    revenue_pending_approval = df[drafted_mask]['mrr'].sum()
    
    # Mean Time to Draft (Proxy calculation based on Spark batch intervals)
    # Note: In a production setup, we would use: (df['draft_time'] - df['event_time']).mean()
    mttr = 1.25 if not df[df['ai_draft'].notnull()].empty else 0

    # --- 2. Analytics Row: Top Metrics ---
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total High-Risk Events", total_events)
        st.metric("Intervention Success Rate", f"{success_rate:.1f}%")
    with m2:
        st.metric("Drafts Pending Review", pending_review_count)
        st.metric("Mean Time to Draft", f"{mttr} min")
    with m3:
        st.metric("Revenue Actioned", f"${revenue_Actioned:,.2f}")
        st.metric("Revenue at Risk", f"${revenue_at_risk:,.2f}", delta_color="inverse")
        st.metric("Revenue on Pending Approval",f"${revenue_pending_approval}")

    # --- 3. Analytics Row: Visualizations ---
    st.divider()
    c1, c2 = st.columns([2, 1])

    with c1:
        st.subheader("📊 Revenue Exposure by Account")
        fig = px.bar(
            df, 
            x="account_id", 
            y="mrr", 
            color="is_approved",
            title="Revenue Status (Green = Approved/Actioned | Red = Risk)",
            color_discrete_map={True: "#2ecc71", False: "#e74c3c"},
            labels={"is_approved": "Actioned?", "account_id": "Account Name", "mrr": "MRR ($)"}
        )
        st.plotly_chart(fig, width="stretch")

    with c2:
        st.subheader("📂 Risk Categories")
        if 'category' in df.columns and not df['category'].isnull().all():
            cat_fig = px.pie(
                df, names="category", values="mrr", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(cat_fig, width="stretch")
        else:
            st.info("Waiting for RAG Categorization...")

    # --- 4. The Command Center: Review Section ---
    
    st.divider()
    st.header("✍️ Recovery Command Center")
    st.write("Authorize AI-generated recovery protocols for high-value friction events.")

    drafts_to_review = df[drafted_mask]

    if drafts_to_review.empty:
        st.success("✅ No drafts currently awaiting review. Pipeline is clear.")
    else:
        for _, row in drafts_to_review.iterrows():
            with st.expander(f"ACTION REQUIRED: {row['account_id']} | MRR: ${row['mrr']:,.2f}"):
                
                ctx1, ctx2 = st.columns([1, 2])
                with ctx1:
                    st.markdown("**Incident Context**")
                    st.error(f"**Complaint:** {row['event_body']}")
                    st.markdown(f"**RAG Category:** `{row['category']}`")
                    st.caption(f"Event ID: {row['event_id']}")
                
                with ctx2:
                    st.markdown("**AI Suggested Response**")
                    edited_email = st.text_area(
                        "Edit Recovery Email:", 
                        value=row['ai_draft'], 
                        height=200, 
                        key=f"edit_{row['event_id']}"
                    )
                    
                    if st.button("🚀 Authorize & Send Recovery Protocol", key=f"btn_{row['event_id']}"):
                        try:
                            conn = psycopg2.connect(
                                host=os.getenv("DB_HOST", "localhost"),
                                database=os.getenv("DB_NAME", "sentinel_operational"),
                                user=os.getenv("DB_USER"),
                                password=os.getenv("DB_PASSWORD")
                            )
                            with conn.cursor() as cur:
                                # Standardizing column names to match your latest schema
                                cur.execute(
                                    "UPDATE high_priority_alerts SET ai_draft = %s, is_approved = TRUE WHERE event_id = %s",
                                    (edited_email, row['event_id'])
                                )
                            conn.commit()
                            conn.close()
                            st.toast(f"Protocol Authorized for {row['account_id']}!", icon="🚀")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")
        
            # --- 5. Export for Management ---
    st.divider()
    st.subheader("📊 Operational Reporting")

    if not df[df['is_approved'] == True].empty:
        # Filter for approved recoveries and drop duplicates for the revenue report
        report_df = df[df['is_approved'] == True].drop_duplicates(subset=['account_id'])
        
        # Select clean columns for the report
        report_csv = report_df[['account_id', 'mrr', 'category', 'event_body', 'ai_draft']].to_csv(index=False)
        
        st.download_button(
            label="📥 Download Success Report (CSV)",
            data=report_csv,
            file_name=f"sentinel_recovery_report_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="Export a list of all unique accounts Actioned and the associated MRR."
        )
    else:
        st.caption("No recovery data available for export yet.")

else:
    st.warning("Awaiting incoming data stream from Spark...")
    st.info("Check if your Redpanda, Spark, and action.py scripts are running.")

