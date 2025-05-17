def moving_diff_sum_time(arr, timestamps, window_ms=600, threshold=50, min_peak=10):
    import numpy as np
    arr = np.array(arr)
    timestamps = np.array(timestamps)
    window_us = window_ms * 1000
    result = np.zeros_like(arr, dtype=bool)
    for i in range(len(arr)):
        # Trova gli indici nella finestra temporale centrata su i
        mask = np.abs(timestamps - timestamps[i]) <= window_us // 2
        idx = np.where(mask)[0]
        if len(idx) > 2:
            window_arr = arr[idx]
            diffs = np.diff(window_arr)

            selected_diffs = np.abs(diffs)
            selected_diffs = selected_diffs[selected_diffs > min_peak]
            if np.sum(selected_diffs) > threshold:
                result[i] = True
    return result

def mean_z_in_window(z, t, center_idx, window_ms=1000):
    import numpy as np
    """
    Calcola la media di z in una finestra temporale di window_ms millisecondi centrata su t[center_idx].
    """
    t0 = t[center_idx]
    window_us = window_ms * 1000
    mask = np.abs(t - t0) <= window_us // 2
    return np.mean(z[mask])

def find_crash(ulog):
    import numpy as np
    result = {}

    # Trova i dati di sensor_accel
    for d in ulog.data_list:
        if d.name == "sensor_accel":
            t = np.array(d.data["timestamp"])
            x = np.array(d.data["x"])
            y = np.array(d.data["y"])
            z = np.array(d.data["z"])

            # Crash per modulo accelerazione (classico)
            accel_norm = np.sqrt(x**2 + y**2 + z**2)
            crash_modulo = accel_norm > 40  # Soglia esempio

            # Crash per doppia inversione: somma delle differenze su finestra temporale
            crash_inversion = (
                moving_diff_sum_time(x, t, window_ms=600, threshold=50) |
                moving_diff_sum_time(y, t, window_ms=600, threshold=50) |
                moving_diff_sum_time(z, t, window_ms=600, threshold=50)
            )

            crash_detected = (crash_modulo | crash_inversion).astype(int)

            # Filtro: la media di z entro 1000ms dal crash deve essere > -5
            filtered_crash = np.zeros_like(crash_detected)
            for i in range(len(crash_detected)):
                if crash_detected[i]:
                    mean_z = mean_z_in_window(z, t, i, window_ms=1000)
                    if mean_z > -5:
                        filtered_crash[i] = 1

            result["crash_detected"] = (t, filtered_crash)
            break

    return result

def find_motor_saturation(ulog, threshold=95, event=None):
    import numpy as np
    result = {}
    # Usa time_window_sec solo se passato tramite event, altrimenti default 10
    time_window_sec = 10
    if event is not None:
        threshold = event.get('threshold', threshold)
        time_window_sec = event.get('time_window_sec', time_window_sec)
    for d in ulog.data_list:
        if d.name == "esc_status":
            t = np.array(d.data["timestamp"])
            all_saturation = np.zeros_like(t, dtype=bool)
            for i in range(8):
                key = f"esc[{i}].esc_power"
                if key in d.data:
                    esc_power = np.array(d.data[key])
                    all_saturation |= (esc_power >= threshold)
            event_mask = np.zeros_like(all_saturation, dtype=int)
            last_event_time = -np.inf
            for idx, (sat, ts) in enumerate(zip(all_saturation, t)):
                if sat:
                    if (ts - last_event_time) > time_window_sec * 1e6:
                        event_mask[idx] = 1
                        last_event_time = ts
            result["motor_saturation"] = (t, event_mask)
            return result
    return {}

def find_innovation_max(ulog, base_name):
    """
    Cerca tutti i campi estimator_innovation_test_ratios che iniziano con base_name
    e restituisce il massimo tra questi per ogni time point, escludendo gli infiniti.
    """
    import numpy as np
    result = {}
    for d in ulog.data_list:
        if d.name == "estimator_innovation_test_ratios":
            t = np.array(d.data["timestamp"])
            # Trova tutti i campi che iniziano con base_name
            fields = [k for k in d.data.keys() if k.startswith(base_name)]
            if not fields:
                return {}
            arrs = [np.array(d.data[k]) for k in fields]

            arrs_stack = np.vstack(arrs)
            # Sostituisci infiniti con nan per poterli ignorare nel massimo
            arrs_stack = np.where(np.isinf(arrs_stack), np.nan, arrs_stack)
            max_arr = np.nanmax(arrs_stack, axis=0)
            result[base_name] = (t, max_arr)
            return result
    return {}

def compute_complex_data(ulog, events):
    result = {}

    # Crash detection
    result.update(find_crash(ulog))

    # Motor saturation detection
        # Trova l'evento di motor saturation
    motor_sat_event = None
    for event in events:
        if event.get('id', '') == 'motor_saturation' or \
           event.get('monitored_param', '').endswith('motor_saturation'):
            motor_sat_event = event
            break

    # Motor saturation detection, passa l'evento se trovato
    if motor_sat_event is not None:
        result.update(find_motor_saturation(ulog, event=motor_sat_event))
    else:
        result.update(find_motor_saturation(ulog))

    # Innovation test ratios (max tra i campi corrispondenti)
    for base in [
        "ev_hpos", "ev_hvel", "ev_vpos", "ev_vvel",
        "gps_hpos", "gps_hvel", "gps_vpos", "gps_vvel",
        "mag", "terr_flow", "flow"
    ]:
        result.update(find_innovation_max(ulog, base))

    return result