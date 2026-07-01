import time
from datetime import datetime
from zoneinfo import ZoneInfo
map_months = {}
map_months[1] = "january"
map_months[2] = "february"
map_months[3] = "march"
map_months[4] = "april"
map_months[5] = "may"
map_months[6] = "june"
map_months[7] = "july"
map_months[8] = "august"
map_months[9] = "september"
map_months[10] = "october"
map_months[11] = "november"
map_months[12] = "december"

map_hours = {}
map_hours[0] = "12am"
map_hours[1] = "1am"
map_hours[2] = "2am"
map_hours[3] = "3am"
map_hours[4] = "4am"
map_hours[5] = "5am"
map_hours[6] = "6am"
map_hours[7] = "7am"
map_hours[8] = "8am"
map_hours[9] = "9am"
map_hours[10] = "10am"
map_hours[11] = "11am"
map_hours[12] = "12pm"
map_hours[13] = "1pm"
map_hours[14] = "2pm"
map_hours[15] = "3pm"
map_hours[16] = "4pm"
map_hours[17] = "5pm"
map_hours[18] = "6pm"
map_hours[19] = "7pm"
map_hours[20] = "8pm"
map_hours[21] = "9pm"
map_hours[22] = "10pm"
map_hours[23] = "11pm"

#sample june-30-2026-8pm-et

def parse_time_name_hourly():
    et_now = datetime.now(ZoneInfo("America/New_York"))

    split1 = str(et_now).split(" ")
    date = split1[0]
    time = split1[1]

    split2 = date.split("-")
    year = split2[0]
    month = map_months[int(split2[1])]
    day = split2[2]


    split3 = time.split("-")
    hour, minute, secondandmilisecond = split3[0].split(":")
    second, milisecond = secondandmilisecond.split(".")

    hourampm = map_hours[int(hour)]
    ret = {
        "hourly_name": f"{month}-{day}-{year}-{hourampm}-et",
        "timestamp": et_now.timestamp(),
    }
    #print(ret)
    return ret
