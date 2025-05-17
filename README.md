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
