import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px

st.set_page_config(page_title="Sentinel-Flow Recovery Dashboard", layout="wide")

# Database Connection
def get_data():
    conn = psycopg2.connect(
        host="localhost",
        database="sentinel_operational",
        user="maha_admin",
        password="sentinel_pass",
        port="5432"
    )
    df = pd.read_sql("SELECT * FROM high_priority_alerts", conn)
    conn.close()
    return df

st.title("🛡️ Sentinel-Flow: Revenue Recovery Engine")
st.markdown("Real-time monitoring of high-value customer friction.")

try:
    df = get_data()

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Alerts Identified", len(df))
    with col2:
        pending_mrr = df[df['status'] == 'pending']['mrr'].sum()
        st.metric("Revenue at Risk (Pending)", f"${pending_mrr:,.2f}")
    with col3:
        completed_count = len(df[df['status'] == 'completed'])
        st.metric("AI Recovery Drafts Ready", completed_count)

    # Visualization
    st.subheader("Alert Distribution by Account")
    fig = px.bar(df, x="account_id", y="mrr", color="status", title="MRR by Account and Status")
    st.plotly_chart(fig, width="stretch")

    # The AI Output Table
    st.subheader("Latest AI Recovery Drafts")

    # We create the subset of data first
    output_df = df[df['status'] == 'completed'][['account_id', 'mrr', 'recovery_draft']].tail(5)

    # Use st.dataframe for a cleaner look with the index hidden
    st.dataframe(output_df, hide_index=True, width="stretch")

except Exception as e:
    st.error(f"Waiting for data... {e}")

st.subheader("✍️ Final Review: Edit & Approve Recovery Emails")

drafts_to_review = df[df['status'] == 'completed']

if drafts_to_review.empty:
    st.info("No drafts currently awaiting review.")
else:
    for index, row in drafts_to_review.iterrows():
        # Create a unique key for each widget based on event_id
        with st.expander(f"Review Draft for {row['account_id']} - ${row['mrr']} MRR"):
            st.write(f"**Raw Customer Complaint:** {row['event_body']}")
            
            # 1. Editable Text Area
            # The user can now click inside this box and change the text
            edited_email = st.text_area(
                "Edit Email Body:", 
                value=row['recovery_draft'], 
                height=250, 
                key=f"edit_{row['event_id']}"
            )
            
            # 2. Approve & Send Button
            if st.button(f"Approve & Send to {row['account_id']}", key=f"btn_{row['event_id']}"):
                with psycopg2.connect(
                    host="localhost",
                    database="sentinel_operational",
                    user="maha_admin",
                    password="sentinel_pass"
                ) as conn:
                    with conn.cursor() as cur:
                        # Save the EDITED email and update status
                        cur.execute(
                            "UPDATE high_priority_alerts SET recovery_draft = %s, status = 'sent' WHERE event_id = %s",
                            (edited_email, row['event_id'])
                        )
                st.success(f"Successfully updated and sent email for {row['account_id']}!")
                st.rerun()