import sys
import yaml
from pyulog import ULog
import operator
import re
from complex_data import compute_complex_data
from nav_state import add_nav_state_changes_to_events

OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}

CONSTANTS = {
    "LOW_BATT_VOLT": 0.0,
    "CRIT_BATT_VOLT": 0.0,
    "GPS_ENABLED": 0,
    "MAG_ENABLED": 0,
    "GPS_YAW_ENABLED": 0,
    "GPS_ALT_ENABLED": 0,
    "GPS_POS_ENABLED": 0,
    "EV_YAW_ENABLED": 0,
    "EV_VEL_ENABLED": 0,
    "EV_ALT_ENABLED": 0,
    "EV_POS_ENABLED": 0,
    "BARO_ENABLED": 0,
}

COLORS = {
    "info": "\033[0m",      # Bianco (default)
    "warning": "\033[93m",  # Giallo
    "critical": "\033[91m", # Rosso
}
RESET = "\033[0m"


# parse a condition string and return a list of tuples (left, op, val)
def parse_condition(cond_str):
    # supports multiple conditions with 'and'
    conds = [c.strip() for c in cond_str.split('and')]
    ops_vals = []
    for cond in conds:
        # first tryes with value
        m = re.match(r"value\s*([=!<>]+)\s*([A-Za-z0-9_.-]+)", cond)
        if m:
            op, val = m.group(1), m.group(2)
            left = "value"
        else:
            # try with constant
            m2 = re.match(r"([A-Za-z0-9_.-]+)\s*([=!<>]+)\s*([A-Za-z0-9_.-]+)", cond)
            if not m2:
                raise ValueError(f"Condizione non valida: {cond}")
            left, op, val = m2.group(1), m2.group(2), m2.group(3)
        # detectes constants
        if val in CONSTANTS:
            val = CONSTANTS[val]
        elif val.replace('.', '', 1).isdigit():
            val = float(val) if '.' in val else int(val)
        if left in CONSTANTS:
            left = CONSTANTS[left]
        ops_vals.append((left, OPS[op], val))
    return ops_vals

# get a log parameter value by name
def get_param_data(ulog, param):
    topic, field = param.split('.', 1)
    for d in ulog.data_list:
        if d.name == topic and field in d.data:
            return d.data['timestamp'], d.data[field]
    return None, None

# get a px4 parameter value by name
def get_param_value(ulog, param_name):
    params = dict(ulog.initial_parameters)
    for name in params:
        if name == param_name:
            return params[name]
    return None

# calculate which sensors should be fused in the filter
def get_fusion_flags(ulog):

    gps_mask = int(get_param_value(ulog, "EKF2_GPS_CTRL"))
    baro_ctrl = int(get_param_value(ulog, "EKF2_BARO_CTRL"))
    ev_ctrl = int(get_param_value(ulog, "EKF2_EV_CTRL"))

    sys_has_gps = int(get_param_value(ulog, "SYS_HAS_GPS"))
    sys_has_mag = int(get_param_value(ulog, "SYS_HAS_MAG"))
    sys_has_baro = int(get_param_value(ulog, "SYS_HAS_BARO"))

    def bit(mask, n):
        return (mask & (1 << n)) != 0

    CONSTANTS["GPS_ENABLED"]      = sys_has_gps > 0
    CONSTANTS["GPS_POS_ENABLED"]  = sys_has_gps > 0 and bit(gps_mask, 0)
    CONSTANTS["GPS_ALT_ENABLED"]  = sys_has_gps > 0 and bit(gps_mask, 1)
    CONSTANTS["GPS_VEL_ENABLED"]  = sys_has_gps > 0 and bit(gps_mask, 2)
    CONSTANTS["GPS_YAW_ENABLED"]  = sys_has_gps > 0 and bit(gps_mask, 3)

    CONSTANTS["MAG_ENABLED"]      = sys_has_mag > 0
    CONSTANTS["BARO_ENABLED"]     = sys_has_baro > 0 and baro_ctrl > 0

    CONSTANTS["EV_POS_ENABLED"]   = bit(ev_ctrl, 0)
    CONSTANTS["EV_ALT_ENABLED"]   = bit(ev_ctrl, 1)
    CONSTANTS["EV_VEL_ENABLED"]   = bit(ev_ctrl, 2)
    CONSTANTS["EV_YAW_ENABLED"]   = bit(ev_ctrl, 3)

# set battery low and critical voltage values based on px4 parameters
def set_battery_constants(ulog):
    n_cells = get_param_value(ulog, "BAT1_N_CELLS")
    v_charged = get_param_value(ulog, "BAT1_V_CHARGED")
    v_empty = get_param_value(ulog, "BAT1_V_EMPTY")
    if n_cells is not None and v_charged is not None:
        try:
            n_cells = float(n_cells)
            v_charged = float(v_charged)
            low = n_cells * (v_empty + ((v_charged - v_empty) * 0.3))
            crit = n_cells * (v_empty + ((v_charged - v_empty) * 0.1))
            CONSTANTS["LOW_BATT_VOLT"] = low
            CONSTANTS["CRIT_BATT_VOLT"] = crit
        except Exception:
            pass

# print a string with a color based on severity
def print_colored(severity, timestamp, message, rel_time=None):
    color = COLORS.get(severity, COLORS["info"])
    label = severity.upper()
    if rel_time is not None:
        print(f"{color}[{timestamp:.3f}s | {rel_time:.3f}s] {label}: {message}{RESET}")
    else:
        print(f"{color}[{timestamp:.3f}s] {label}: {message}{RESET}")




# main function to parse the ulog file and detect events
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 px4_log_parser.py <logfile.ulg>")
        sys.exit(1)

    log_file = sys.argv[1]

    # Load the events from the YAML file
    with open('events.yaml', 'r') as f:
        events = yaml.safe_load(f)['events']

    ulog = ULog(log_file)

    # Set battery constants and fusion flags
    set_battery_constants(ulog)
    get_fusion_flags(ulog)

    #calculate more complex data parameters
    complex_data = compute_complex_data(ulog, events)

    detected_events = []

    # Loop through each event and check conditions
    for event in events:
        param = event['monitored_param']
        cond = event['condition']
        severity = event.get('severity', 'info')
        ops_vals = parse_condition(cond)

        # Check if the parameter is a complex data field
        if param.startswith("complex_data."):
            field = param.split('.', 1)[1]
            if field in complex_data:
                timestamps, values = complex_data[field]
            else:
                continue
        else:   # simple log parameter to check
            timestamps, values = get_param_data(ulog, param)

        if timestamps is None:
            continue

        # converts all infinite values in nan to avoid false positives
        import numpy as np
        values = np.array(values, dtype=float)
        values[np.isinf(values)] = np.nan

        prev = False
        last_event_time = -np.inf
        time_window_sec = event.get("time_window_sec", 0)
        for t, v in zip(timestamps, values):
            if np.isnan(v):
                continue
            try:
                res = all((v if left == "value" else left) == val if op == OPS["=="] else op((v if left == "value" else left), val)
                        for left, op, val in ops_vals)
            except Exception:
                continue
            # Segnala solo sul fronte di salita e rispetta la finestra temporale
            if not prev and res and (t/1e6 - last_event_time >= time_window_sec):
                detected_events.append({
                    "timestamp": t/1e6,
                    "severity": severity,
                    "message": event['message']
                })
                last_event_time = t/1e6
            prev = res

    # add navigation state changes
    add_nav_state_changes_to_events(ulog, detected_events)

    # sort events by timestamp
    detected_events.sort(key=lambda e: e["timestamp"])
    start_time = ulog.start_timestamp / 1e6 if hasattr(ulog, "start_timestamp") else 0

    # print all events
    for e in detected_events:
        rel_time = e["timestamp"] - start_time
        print_colored(e["severity"], e["timestamp"], e["message"], rel_time)

if __name__ == "__main__":
    main()