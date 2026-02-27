import streamlit as st
import pandas as pd
import psycopg2
import os
import plotly.express as px
import time
from sqlalchemy import create_engine

# --- 1. Page Config (MUST BE FIRST) ---
st.set_page_config(
    page_title="Sentinel-Flow Control Room", 
    layout="wide", 
    page_icon="Real-Time AI Revenue Protection System🛡️"
)

# --- 2. Sidebar Controls ---
st.sidebar.header("🕹️ Dashboard Controls")
refresh_rate = st.sidebar.slider("Auto-Refresh (seconds)", 5, 60, 10)
auto_refresh = st.sidebar.checkbox("Enable Auto-Refresh", value=True)

# --- 3. Custom Styling ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    [data-testid="stMetric"] {
        background-color: #1a1c24 !important; 
        padding: 20px; border-radius: 12px; border: 1px solid #3d4451;
    }
    [data-testid="stMetricLabel"] { color: #9ca3af !important; font-weight: 600; }
    [data-testid="stMetricValue"] { color: #3b82f6 !important; }
    </style>
    """, unsafe_allow_html=True)

def get_db_data(table_name):
    try:
        engine = create_engine("postgresql://maha_admin:sentinel_pass@127.0.0.1:5432/sentinel_operational")
        df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        engine.dispose()
        
        if df.empty:
            return df

        # Table-specific sorting and deduplication
        if table_name == 'high_priority_alerts':
            df['has_draft'] = df['ai_draft'].notnull().astype(int)
            df = df.sort_values(['has_draft', 'timestamp'], ascending=[False, False])
            df = df.drop_duplicates(subset=['account_id', 'category'])
            df = df.drop(columns=['has_draft'])

        elif table_name == 'friction_loops':
            df = df.sort_values('window_start', ascending=False)
            df = df.drop_duplicates(subset=['account_id', 'category'])

        elif table_name == 'silent_churners':
            df = df.sort_values('window_start', ascending=False)
            df = df.drop_duplicates(subset=['account_id'])
            
        return df
    except Exception as e:
        st.sidebar.error(f"Error in {table_name}: {e}")
        return pd.DataFrame()

def update_approval(table_name, row_data, final_draft):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "sentinel_operational"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()
    if table_name == "high_priority_alerts":
        cur.execute(f"UPDATE {table_name} SET ai_draft = %s, is_approved = TRUE WHERE event_id = %s", (final_draft, row_data['event_id']))
    elif table_name == "friction_loops":
        cur.execute(f"UPDATE {table_name} SET ai_draft = %s, is_approved = TRUE WHERE account_id = %s AND category = %s AND window_start = %s", (final_draft, row_data['account_id'], row_data['category'], row_data['window_start']))
    elif table_name == "silent_churners":
        cur.execute(f"UPDATE {table_name} SET ai_draft = %s, is_approved = TRUE WHERE account_id = %s AND window_start = %s", (final_draft, row_data['account_id'], row_data['window_start']))
    conn.commit()
    cur.close(); conn.close()

# --- 5. Main UI Logic ---
st.title("Real-Time AI Revenue Protection System 🛡️")

df_reactive = get_db_data("high_priority_alerts")
df_loops = get_db_data("friction_loops")
df_churn = get_db_data("silent_churners")

# Check if we have data in ANY table
if not df_reactive.empty or not df_loops.empty or not df_churn.empty:
    
    # GLOBAL METRICS (Handle empty df_reactive safely)
    total_events = len(df_reactive) if not df_reactive.empty else 0
    success_rate = (len(df_reactive[df_reactive['is_approved'] == True]) / total_events * 100) if total_events > 0 else 0
    revenue_Actioned = df_reactive[df_reactive['is_approved'] == True].drop_duplicates(subset=['account_id'])['mrr'].sum() if not df_reactive.empty else 0
    
    # De-duplicated Revenue at Risk across all proactive/reactive lanes
    all_pending = pd.concat([
        df_reactive[df_reactive['is_approved'] == False][['account_id', 'mrr']] if not df_reactive.empty else pd.DataFrame(),
        df_loops[df_loops['is_approved'] == False][['account_id', 'mrr']] if not df_loops.empty else pd.DataFrame(),
        df_churn[df_churn['is_approved'] == False][['account_id', 'mrr']] if not df_churn.empty else pd.DataFrame()
    ]).drop_duplicates(subset=['account_id'])
    
    revenue_at_risk = all_pending['mrr'].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Risk Events", total_events + len(df_loops) + len(df_churn))
    m2.metric("Success Rate", f"{success_rate:.1f}%")
    m3.metric("Actioned", f"${revenue_Actioned:,.2f}")
    m4.metric("At Risk", f"${revenue_at_risk:,.2f}")

    st.divider()

    tab1, tab2, tab3,tab4 = st.tabs(["Ticket Action", "Systemic Failure Alert", "Silent Churn Risk (ghosting👻)", "Executive Overview"])

    with tab1:
        if not df_reactive.empty:
            st.subheader("Ticket Risk Status")
            fig_re = px.bar(
                df_reactive, 
                x="account_id", 
                color="is_approved",
                title="Ticket Frequency & Approval Status",
                color_discrete_map={True: "#2ecc71", False: "#e74c3c"},
                labels={"count": "Number of Tickets", "is_approved": "Fixed?"},
                barmode="stack" 
            )
            st.plotly_chart(fig_re, width="stretch")

        drafts = df_reactive[
            (df_reactive['ai_draft'].notnull()) & 
            (df_reactive['ai_draft'] != '') & 
            (df_reactive['is_approved'] == False)
        ] if not df_reactive.empty else pd.DataFrame()

        if drafts.empty:
            st.success("All Reactive Tickets Resolved!")
        else:
            for _, row in drafts.iterrows():
                with st.expander(f"ACTION: {row['account_id']} (${row['mrr']:,.0f})"):
                    c1, c2 = st.columns([1, 2])
                    c1.error(f"**Issue:** {row['event_body']}")
                    edited = c2.text_area(
                        "Refine AI Draft:", 
                        row['ai_draft'], 
                        height=500, 
                        key=f"re_{row['event_id']}"
                    )
                    if c2.button("Authorize Fix", key=f"btn_re_{row['event_id']}"):
                        update_approval("high_priority_alerts", row, edited)
                        st.rerun()
    with tab2:

        if not df_loops.empty:
            st.subheader("Systemic Friction Status")
            fig_loops = px.bar(
                df_loops, 
                x="account_id", 
                color="is_approved",
                color_discrete_map={True: "#2ecc71", False: "#e74c3c"},
                barmode="stack"
            )
            st.plotly_chart(fig_loops, width="stretch")

        pending_loops = df_loops[df_loops['is_approved'] == False] if not df_loops.empty else pd.DataFrame()
        if pending_loops.empty: st.info("No active friction loops")
        else:
            for _, row in pending_loops.iterrows():
                uid = f"{row['account_id']}_{row['category']}_{row['window_start']}"
                with st.expander(f"⚠️ {row['account_id']} | {row['incident_count']} Repeats"):
                    c1, c2 = st.columns([1, 2])
                    c1.warning(f"**Issue:** {row['category']}")
                    edited = c2.text_area("Refine Story:", row['ai_draft'], height=450, key=f"txt_{uid}")
                    if c2.button("🚀 Send Escalation", key=f"btn_{uid}"):
                        update_approval("friction_loops", row, edited)
                        st.rerun()

    with tab3:
        if not df_churn.empty:
            st.subheader("Behavioral Health Status")
            fig_churn = px.bar(
                df_churn, 
                x="account_id", 
                color="is_approved",
                color_discrete_map={True: "#2ecc71", False: "#e74c3c"},
                barmode="stack"
            )
            st.plotly_chart(fig_churn, width="stretch")

        pending_churn = df_churn[df_churn['is_approved'] == False] if not df_churn.empty else pd.DataFrame()
        if pending_churn.empty: st.info("No churn risks.")
        else:
            for _, row in pending_churn.iterrows():
                uid = f"{row['account_id']}_{row['window_start']}"
                with st.expander(f"👻 {row['account_id']} engagement"):
                    c1, c2 = st.columns([1, 2])
                    c1.info(f"Logins: {row['login_count']} | Uses: 0")
                    edited = c2.text_area("Refine Script:", row['ai_draft'], height=450, key=f"churn_{uid}")
                    if c2.button("Send Outreach", key=f"btn_churn_{uid}"):
                        update_approval("silent_churners", row, edited)
                        st.rerun()
    with tab4:
        st.header("Executive Control Room")
        
        # 1. Logic to prevent the Future Warning
        dfs_to_combine = []
        if not df_reactive.empty: dfs_to_combine.append(df_reactive[['account_id', 'mrr', 'is_approved', 'ai_draft']])
        if not df_loops.empty:    dfs_to_combine.append(df_loops[['account_id', 'mrr', 'is_approved', 'ai_draft']])
        if not df_churn.empty:    dfs_to_combine.append(df_churn[['account_id', 'mrr', 'is_approved', 'ai_draft']])

        if dfs_to_combine:
            combined_all = pd.concat(dfs_to_combine, ignore_index=True).drop_duplicates(subset=['account_id'])
            combined_all['status'] = combined_all['is_approved'].map({True: 'Actioned', False: 'At Risk'})
            
            # --- Row 1: Holistic KPIs ---
            c1, c2 = st.columns(2)
        
            with c1:
                st.subheader("🎯 Risk Distribution by Alert Type")
                
                # Build a breakdown by source
                donut_data = []
                
                if not df_reactive.empty:
                    donut_data.append({
                        'type': 'Ticket Recovery',
                        'mrr': df_reactive[df_reactive['is_approved'] == False]['mrr'].sum()
                    })
                if not df_loops.empty:
                    donut_data.append({
                        'type': 'Systemic Failure',
                        'mrr': df_loops[df_loops['is_approved'] == False]['mrr'].sum()
                    })
                if not df_churn.empty:
                    donut_data.append({
                        'type': 'Silent Churn Risk',
                        'mrr': df_churn[df_churn['is_approved'] == False]['mrr'].sum()
                    })
                
                donut_df = pd.DataFrame(donut_data)
                
                if not donut_df.empty and donut_df['mrr'].sum() > 0:
                    fig_donut = px.pie(
                        donut_df,
                        values='mrr',
                        names='type',
                        hole=.6,
                        color='type',
                        color_discrete_map={
                            'Ticket Recovery': '#e74c3c',
                            'Systemic Failure': '#f39c12',
                            'Silent Churn Risk': '#9b59b6'
                        }
                    )
                    fig_donut.update_traces(textinfo='percent+label')
                    fig_donut.update_layout(
                        showlegend=False, 
                        margin=dict(t=30, b=0, l=0, r=0)
                    )
                    st.plotly_chart(fig_donut, width="stretch")
                else:
                    st.info("No active risks to display.")

            with c2:
                st.subheader("🏗️ Revenue Pipeline Funnel")
                funnel_data = dict(
                    number=[
                        combined_all['mrr'].sum(),
                        combined_all[combined_all['ai_draft'].notnull() & (combined_all['ai_draft'] != '')]['mrr'].sum(),
                        combined_all[combined_all['is_approved'] == True]['mrr'].sum()
                    ],
                    stage=["Total Revenue Risk Detected", "AI Draft Generated", "Revenue Actioned"]
                )
                fig_funnel = px.funnel(funnel_data, x='number', y='stage', color_discrete_sequence=['#3b82f6'])
                st.plotly_chart(fig_funnel, width="stretch")

            st.divider()

            # --- Row 2: Detailed Exposure & Reporting ---
            v1, v2 = st.columns(2)
            with v1:
                st.subheader("Top Risk Exposure by Account")
                if not all_pending.empty:
                    all_pending_sorted = all_pending.sort_values(by='mrr', ascending=False).head(10)
                    fig_bar = px.bar(
                        all_pending_sorted, x="account_id", y="mrr", 
                        title="Top 10 High-Risk Accounts",
                        color_discrete_sequence=["#e74c3c"]
                    )
                    st.plotly_chart(fig_bar, width="stretch")

            with v2:
                st.subheader("Operational Success Report")
                all_approved = combined_all[combined_all['is_approved'] == True]
                if not all_approved.empty:
                    csv_data = all_approved.to_csv(index=False)
                    st.download_button("📥 Download Action Report", csv_data, f"Action_{int(time.time())}.csv", "text/csv")
                    st.dataframe(all_approved[['account_id', 'mrr']], width="stretch")
                else:
                    st.info("No accounts Actioned yet. Approvals will appear here.")
else:
    st.info("Awaiting initial data stream to populate executive metrics...")

# --- 6. Final Auto-Refresh Trigger (Placed at bottom) ---
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()