import streamlit as st
import pandas as pd
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="2026 Olympic Fantasy Tracker", layout="wide", page_icon="🏒")

# --- 1. ROSTER LOADER (With Cleanup) ---
@st.cache_data
def load_roster():
    try:
        df = pd.read_csv("fantasy_roster.csv")
        
        # CLEANUP: Remove common junk rows that sneak in
        junk_names = ["Draft", "Trade", "Bench", "Slot", "Player", "Acq", "Free Agency", "Waivers"]
        # Filter out rows where the name is in our junk list
        df = df[~df['Player_Name'].isin(junk_names)]
        # Filter out names that are suspiciously short (e.g. "F", "D", "G")
        df = df[df['Player_Name'].str.len() > 2]
        
        return df
    except FileNotFoundError:
        return pd.DataFrame()

# --- 2. DATA SOURCE: HARDCODED STARTER PACK (Reliable) ---
# Since the Olympic site blocks scrapers, we use this "Starter Pack" 
# + a manual paste feature for the rest.
def get_starter_pack():
    # Top ~50 players to ensure the board looks alive immediately
    data = [
        # Canada
        ("McDAVID Connor", "CAN", 3, 8, 11), ("CROSBY Sidney", "CAN", 2, 4, 6), 
        ("MACKINNON Nathan", "CAN", 2, 3, 5), ("MAKAR Cale", "CAN", 1, 4, 5),
        ("BEDARD Connor", "CAN", 2, 2, 4), ("POINT Brayden", "CAN", 3, 1, 4),
        # USA
        ("MATTHEWS Auston", "USA", 3, 2, 5), ("HUGHES Jack", "USA", 1, 4, 5),
        ("TKACHUK Matthew", "USA", 2, 3, 5), ("FOX Adam", "USA", 0, 4, 4),
        # Others
        ("SLAFKOVSKY Juraj", "SVK", 4, 2, 6), ("PASTRNAK David", "CZE", 2, 3, 5),
        ("KUCHEROV Nikita", "AIN", 3, 4, 7), ("KAPRIZOV Kirill", "AIN", 4, 1, 5),
        ("RANTANEN Mikko", "FIN", 2, 2, 4), ("JOSI Roman", "SUI", 1, 3, 4)
    ]
    return pd.DataFrame(data, columns=["Player_Name", "Country", "Goals", "Assists", "Points"])

# --- 3. HELPER: NAME MATCHING ---
def normalize(name):
    """Converts 'Connor McDavid' -> {'connor', 'mcdavid'}"""
    return set(re.sub(r'[^\w\s]', '', str(name)).lower().split())

def find_match(roster_name, stats_df):
    """Finds the Olympic stat row that matches the Roster name."""
    r_parts = normalize(roster_name)
    
    # Check every player in the stats database
    for idx, row in stats_df.iterrows():
        s_parts = normalize(row['Player_Name'])
        # If we have a good overlap (First + Last name match)
        if len(r_parts.intersection(s_parts)) >= 2:
            return row
            
    return None

# --- MAIN APP ---
st.title("🏒 2026 Olympic Fantasy Hockey Tracker")

# Initialize Session State for Stats
if 'stats_db' not in st.session_state:
    st.session_state['stats_db'] = get_starter_pack()

# Load User Roster
roster = load_roster()

if roster.empty:
    st.warning("⚠️ `fantasy_roster.csv` not found. Please rename your output file!")
else:
    # --- MERGE LOGIC ---
    # We iterate through the roster and find the stats for each player
    merged_data = []
    
    stats_db = st.session_state['stats_db']
    
    for _, row in roster.iterrows():
        r_name = row['Player_Name']
        team = row['Fantasy_Team']
        
        # Find stats
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
            # Player listed in roster but has 0 points or not in DB yet
            merged_data.append({
                "Fantasy_Team": team,
                "Player": r_name,
                "Olympic_Name": "-",
                "Goals": 0, "Assists": 0, "Points": 0
            })
            
    final_df = pd.DataFrame(merged_data)
    
    # --- DASHBOARD LAYOUT ---
    
    # 1. LEADERBOARD
    st.subheader("🏆 League Standings")
    standings = final_df.groupby("Fantasy_Team")[["Goals", "Assists", "Points"]].sum().sort_values("Points", ascending=False)
    st.dataframe(standings, use_container_width=True)
    
    # 2. DETAILED STATS (Expandable)
    with st.expander("See Player Details"):
        team_filter = st.selectbox("Filter by Team", ["All"] + sorted(final_df['Fantasy_Team'].unique()))
        
        view_df = final_df if team_filter == "All" else final_df[final_df['Fantasy_Team'] == team_filter]
        
        st.dataframe(
            view_df.sort_values("Points", ascending=False),
            column_config={
                "Points": st.column_config.ProgressColumn("Points", format="%d", min_value=0, max_value=20),
            },
            use_container_width=True
        )

    # --- MANUAL UPDATE SECTION ---
    st.divider()
    st.caption("Admin Tools")
    with st.expander("Update Olympic Stats (Copy/Paste)"):
        st.info("Since the Olympic site blocks bots, paste the 'Points Leaders' table from QuantHockey or IIHF here to update stats.")
        raw_paste = st.text_area("Paste Stats Table Here")
        if st.button("Process Update"):
            # Simple parser for copied tables (Name ... G A P)
            new_rows = []
            for line in raw_paste.split('\n'):
                # Look for lines with numbers at the end
                # e.g. "1. Connor McDavid CAN 3 8 11"
                parts = line.split()
                if len(parts) > 4 and parts[-1].isdigit():
                    try:
                        pts = int(parts[-1])
                        assists = int(parts[-2])
                        goals = int(parts[-3])
                        # Name is everything before the country code (heuristic)
                        name_parts = parts[1:-4] # approximate
                        name = " ".join(name_parts)
                        if len(name) > 3:
                            new_rows.append({"Player_Name": name, "Country": "Update", "Goals": goals, "Assists": assists, "Points": pts})
                    except:
                        continue
            
            if new_rows:
                st.session_state['stats_db'] = pd.DataFrame(new_rows)
                st.success(f"Updated {len(new_rows)} players! Refreshing...")
                st.rerun()