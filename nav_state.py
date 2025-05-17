def add_nav_state_changes_to_events(ulog, detected_events):
    NAV_STATE_NAMES = {
        0: "MANUAL",
        1: "ALTCTL",
        2: "POSCTL",
        3: "AUTO_MISSION",
        4: "AUTO_LOITER",
        5: "AUTO_RTL",
        10: "ACRO",
        12: "DESCEND",
        13: "TERMINATION",
        14: "OFFBOARD",
        15: "STAB",
        17: "AUTO_TAKEOFF",
        18: "AUTO_LAND",
        19: "AUTO_FOLLOW_TARGET",
        20: "AUTO_PRECLAND",
        21: "ORBIT",
        22: "AUTO_VTOL_TAKEOFF",
    }
    for d in ulog.data_list:
        if d.name == "vehicle_status":
            t = d.data["timestamp"]
            nav_states = d.data["nav_state"]
            prev_state = None
            for ts, state in zip(t, nav_states):
                if prev_state is None or state != prev_state:
                    state_name = NAV_STATE_NAMES.get(state, f"UNKNOWN({state})")
                    detected_events.append({
                        "timestamp": ts/1e6,
                        "severity": "info",
                        "message": f"Nav state changed: {state_name}"
                    })
                    prev_state = state
            break