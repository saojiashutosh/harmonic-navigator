import pytz


def convert_time(time, timezone):
    try:
        return time.astimezone(pytz.timezone(timezone)).strftime("%d-%m-%YT%H:%M:%S%z %Z")
    except:
        return time.strftime("%d-%m-%YT%H:%M:%S%z %Z")
