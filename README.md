# PX4 log file analyzer
An application that parses a .ulg file from PX4 autopilot and detects all important events that happens during a flight. It will then show the list of events sorted by timestamp to quickly identify if something is off.  
The script monitors about 80 parameters such as vehicle status flags, navigation state, vibrations, innovation test ratios, estimator status flags, failsafe flags, battery voltage, gps state and combine some parameters to estrapolate more complex information such as crash detection, motor saturation and more.  
You can also add custom events in the events.yaml file if you need it.  

## Install requirements
You need to have installed in your machine:
* python3
* pip

then install required libraries with  
```bash
pip install -r requirements.txt
```

## Run
To run the script open a terminal and run
```bash
python3 px4_log_parser.py log.ulg
```
where log.ulog is the path to the log file you want to analyze  

## Events
An event is a particular state change or message you want to pay attention to. All events reported must be written in the events.yaml file.  
Each event entry has the following parameters:  
* id: a unique name for the event
* monitored_param: the ulog parameter you want to pay attention to. Supported ones are all log parameter names, complex_data for more advanced data logs and message_log for px4 logged messages 
* condition: a condition string that explaned when the event condition is met. In the condition field, 'value' is a keyword that represents the monitored_param. So if you write "value == 1", it means when the monitored_param parameter is changed to 1 the condition is met. Notice that the event is reported only when the monitored_param changes so it's reported only once for each state change.  
Only for message_log, the condition is a string that needs to be contained in the logged message for the event to be reported (i.e. in the muorb_message event, if a message log contains the string '[muorb]' than it's reported).
* time_window_sec: minimum time window where two events can be reported. For example if two events 'warning_vibration' happens in a time period lower than 5 seconds (time_window_sec for that specific event), than the second event is not reported.
* cause: not used yet
* severity: log severity. Can be info, warning or critical
* message: message that you want to be displayed. Only for message_log you can use the keyword '$' to tell the program to write the full log message instead of a custom one
