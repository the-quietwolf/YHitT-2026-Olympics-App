import streamlit as st
import pandas as pd
import re
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="YHitT Milano Cortina 2026 Stats Tracker", layout="wide", page_icon="🏒")

# --- 1. LOAD USER ROSTER (Server Side Only) ---
# ttl=0 ensures that if you replace the file in the folder, 
# the app picks it up immediately upon refresh.
@st.cache_data(ttl=0)
def load_roster():
    try:
        if not os.path.exists("fantasy_roster.csv"):
            return pd.DataFrame()
            
        df = pd.read_csv("fantasy_roster.csv")
        
        # CLEANUP: Remove common junk rows from the raw export
        if 'Player_Name' in df.columns:
            junk_names = ["Draft", "Trade", "Bench", "Slot", "Player", "Acq", "Free Agency", "Waivers"]
            df = df[~df['Player_Name'].isin(junk_names)]
            df = df[df['Player_Name'].str.len() > 2]
            
        return df
    except Exception as e:
        st.error(f"Error loading roster: {e}")
        return pd.DataFrame()

# --- 2. LOAD QUANTHOCKEY STATS (Server Side Only) ---
@st.cache_data(ttl=0)
def load_stats():
    try:
        if not os.path.exists("mainquant.csv"):
            return pd.DataFrame() # No file found
        
        df = pd.read_csv("mainquant.csv")

        # 1. Clean Column Names (Remove spaces, lowercase)
        df.columns = [str(col).strip().lower() for col in df.columns]
        
        # 2. Map QuantHockey names to App names
        rename_map = {}
        for col in df.columns:
            if col in ['name', 'player', 'skater']:
                rename_map[col] = 'Player_Name'
            elif col in ['g', 'goals']:
                rename_map[col] = 'Goals'
            elif col in ['a', 'assists']:
                rename_map[col] = 'Assists'
            elif col in ['p', 'pts', 'points']:
                rename_map[col] = 'Points'
            elif col in ['team', 'nation', 'country']:
                rename_map[col] = 'Country'

        df.rename(columns=rename_map, inplace=True)
        
        # 3. Validation
        required = ['Player_Name', 'Goals', 'Assists', 'Points']
        missing = [req for req in required if req not in df.columns]
        
        if missing:
            st.error(f"❌ 'mainquant.csv' is missing columns: {missing}")
            return pd.DataFrame()
            
        return df
        
    except Exception as e:
        st.error(f"Error reading stats file: {e}")
        return pd.DataFrame()

# --- 3. HELPER: NAME MATCHING ---
def normalize(name):
    """Converts 'Connor McDavid' -> {'connor', 'mcdavid'}"""
    clean = re.sub(r'[^\w\s]', '', str(name)).lower()
    return set(clean.split())

def find_match(roster_name, stats_df):
    """Finds the Olympic stat row that matches the Roster name."""
    r_parts = normalize(roster_name)
    
    for idx, row in stats_df.iterrows():
        s_parts = normalize(row['Player_Name'])
        if len(r_parts.intersection(s_parts)) >= 2:
            return row
    return None

# --- MAIN APP UI ---
st.title("🥇 🏒 Your Hat's in the Toilet Milano Cortina 2026 Stats Tracker")

# Sidebar: minimal controls
with st.sidebar:
    st.write("Last Updated: Live from file")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# Load Data
roster = load_roster()
stats_db = load_stats()

if roster.empty:
    st.info("⚠️ `fantasy_roster.csv` not found on server.")
    
elif stats_db.empty:
    st.warning("⚠️ Stats file (`mainquant.csv`) not found on server.")
    st.markdown("Please upload the latest QuantHockey export to the repository/folder.")

else:
    # --- MERGE LOGIC ---
    merged_data = []
    
    for i, (index, row) in enumerate(roster.iterrows()):
        r_name = row['Player_Name']
        team = row['Fantasy_Team']
        
        match = find_match(r_name, stats_db)
        
        if match is not None:
            merged_data.append({
                "Fantasy_Team": team,
                "Player": r_name,
                "Olympic_Name": match['Player_Name'],
                "Goals": match['Goals'],
                "Assists": match['Assists'],
                "Points": match['Points']
            })
        else:
            merged_data.append({
                "Fantasy_Team": team,
                "Player": r_name,
                "Olympic_Name": "-",
                "Goals": 0, "Assists": 0, "Points": 0
            })
            
    final_df = pd.DataFrame(merged_data)
    
    # --- DASHBOARD LAYOUT ---
    
    # 1. LEADERBOARD
    st.subheader("Leaderboard")
    standings = final_df.groupby("Fantasy_Team")[["Goals", "Assists", "Points"]].sum().sort_values("Points", ascending=False)
    
    st.dataframe(
        standings, 
        use_container_width=True,
        height=(len(standings) + 1) * 35 
    )
    
    # 2. DETAILED STATS
    st.divider()
    st.subheader("Player Breakdown")
    
    team_list = sorted(final_df['Fantasy_Team'].unique())
    selected_team = st.selectbox("Filter by Fantasy Team", ["All Teams"] + team_list)
    
    if selected_team != "All Teams":
        view_df = final_df[final_df['Fantasy_Team'] == selected_team]
    else:
        view_df = final_df
        
    st.dataframe(
        view_df.sort_values("Points", ascending=False),
        column_config={
            "Points": st.column_config.ProgressColumn(
                "Points", 
                format="%d", 
                min_value=0, 
                max_value=int(final_df['Points'].max()) if not final_df.empty else 10
            ),
        },
        use_container_width=True,
        hide_index=True
    )