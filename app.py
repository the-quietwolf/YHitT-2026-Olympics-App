import streamlit as st
import pandas as pd
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="2026 Olympic Fantasy Tracker", layout="wide", page_icon="🏒")

# --- 1. LOAD USER ROSTER ---
@st.cache_data
def load_roster():
    try:
        df = pd.read_csv("fantasy_roster.csv")
        # CLEANUP: Remove common junk rows
        junk_names = ["Draft", "Trade", "Bench", "Slot", "Player", "Acq", "Free Agency", "Waivers"]
        # Filter out junk and short names
        df = df[~df['Player_Name'].isin(junk_names)]
        df = df[df['Player_Name'].str.len() > 2]
        return df
    except FileNotFoundError:
        st.error("⚠️ `fantasy_roster.csv` not found. Please run the cleaner script first.")
        return pd.DataFrame()

# --- 2. LOAD QUANTHOCKEY STATS ---
@st.cache_data
def load_stats():
    try:
        # Load the file you downloaded
        df = pd.read_csv("mainquant.csv")
        
        # QuantHockey CSVs often have columns like: "Rk", "Name", "GP", "G", "A", "P", "PIM", "+/-"
        # We need to standardize them to: Player_Name, Goals, Assists, Points
        
        # 1. Standardize headers to lowercase
        df.columns = [str(col).strip().lower() for col in df.columns]
        
        # 2. Map known variations to our standard names
        # We look for "name" (or "player"), "g", "a", "p" (or "pts")
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
        
        # 3. Ensure required columns exist (fill with 0 if missing)
        required = ['Player_Name', 'Goals', 'Assists', 'Points']
        if 'Player_Name' not in df.columns:
            st.error("❌ Could not find a 'Name' column in mainquant.csv. Please check the file headers.")
            return pd.DataFrame()
            
        for req in required:
            if req not in df.columns:
                df[req] = 0 # Default to 0 if a column is missing
                
        return df
        
    except FileNotFoundError:
        st.warning("⚠️ `mainquant.csv` not found. Please put the QuantHockey export in this folder.")
        return pd.DataFrame()

# --- 3. HELPER: NAME MATCHING ---
def normalize(name):
    """Converts 'Connor McDavid' -> {'connor', 'mcdavid'}"""
    # Remove punctuation and lowercase
    clean = re.sub(r'[^\w\s]', '', str(name)).lower()
    return set(clean.split())

def find_match(roster_name, stats_df):
    """Finds the Olympic stat row that matches the Roster name."""
    r_parts = normalize(roster_name)
    
    # Iterate through stats database
    for idx, row in stats_df.iterrows():
        s_parts = normalize(row['Player_Name'])
        # If we have a robust overlap (First + Last name match)
        if len(r_parts.intersection(s_parts)) >= 2:
            return row
            
    return None

# --- MAIN APP ---
st.title("🏒 Your Hat's in the Toilet Milano Cortina 2026 Stats Tracker.")

# Load Data
roster = load_roster()
stats_db = load_stats()

if not roster.empty and not stats_db.empty:
    
    # --- MERGE LOGIC ---
    merged_data = []
    
    # Progress Bar for large rosters
    match_progress = st.progress(0, text="Matching players...")
    total_rows = len(roster)
    
    for i, (index, row) in enumerate(roster.iterrows()):
        r_name = row['Player_Name']
        team = row['Fantasy_Team']
        
        # Update progress bar
        match_progress.progress((i + 1) / total_rows, text=f"Matching {r_name}...")
        
        # Find stats
        match = find_match(r_name, stats_db)
        
        if match is not None:
            merged_data.append({
                "Fantasy_Team": team,
                "Player": r_name,
                "Olympic_Name": match['Player_Name'], # Display name from Stats file
                "Goals": match['Goals'],
                "Assists": match['Assists'],
                "Points": match['Points']
            })
        else:
            # Player listed in roster but not in QuantHockey file (maybe hasn't played yet)
            merged_data.append({
                "Fantasy_Team": team,
                "Player": r_name,
                "Olympic_Name": "-",
                "Goals": 0, "Assists": 0, "Points": 0
            })
            
    match_progress.empty() # Hide progress bar when done
    final_df = pd.DataFrame(merged_data)
    
    # --- DASHBOARD LAYOUT ---
    
    # 1. LEADERBOARD
    st.subheader("🏆 League Standings")
    standings = final_df.groupby("Fantasy_Team")[["Goals", "Assists", "Points"]].sum().sort_values("Points", ascending=False)
    
    # Add a "Medal" emoji for top 3
    standings['Rank'] = range(1, len(standings) + 1)
    
    st.dataframe(
        standings[["Goals", "Assists", "Points"]], # Show only data cols
        use_container_width=True,
        height=(len(standings) + 1) * 35 # Auto-adjust height
    )
    
    # 2. DETAILED STATS
    st.divider()
    st.subheader("Player Breakdown")
    
    # Team Filter
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
                max_value=int(final_df['Points'].max())
            ),
        },
        use_container_width=True,
        hide_index=True
    )

elif stats_db.empty:
    st.info("👋 Welcome! Please add your `mainquant.csv` file to the folder to see stats.")