ids = ['1910226553644163074',
       '1910226949393522689',
       '1910227230051180545',
       '1910228638481686530',
       '1910233548914880514',
       '1910234747407888385',
       '1910235142112866305',
       '1910235351605768193',
       '1910237744246104066',
       '1910238444036366337',
       '1910238608683769858',
       '1910238906785538049',
       '1910240459501244417',
       '1910240837345120257',
       '1910243342997164034',
       '1910243558282399745',
       '1910243685260759042',
       '1910246457108500482',
       '1910246652072333314',
       '1910247010106511362',
       '1910244087326740481',
       '1910241072020623362',
       '1910250699676356609',
       '1910250838088388610']

timezones = [
    "Pacific/Pago_Pago",  # UTC-11:00
    "Pacific/Honolulu",   # UTC-10:00
    "America/Adak",
    "America/Anchorage",  # UTC-09:00
    "America/Los_Angeles",# UTC-08:00
    "America/Denver",     # UTC-07:00
    "America/Chicago",    # UTC-06:00
    "America/New_York",   # UTC-05:00
    "America/Halifax",    # UTC-04:00
    "America/Noronha",    # UTC-02:00
    "Etc/GMT+1",
    "Etc/UTC",            # UTC+00:00
    "Africa/Lagos",
    "Europe/Paris",       # UTC+01:00
    "Europe/Moscow",      # UTC+03:00
    "Asia/Dubai",         # UTC+04:00
    "Asia/Karachi",       # UTC+05:00
    "Asia/Dhaka",         # UTC+06:00
    "Asia/Bangkok",       # UTC+07:00
    "Asia/Shanghai",      # UTC+08:00
    "Asia/Tokyo",         # UTC+09:00
    "Australia/Brisbane", # UTC+10:00
    "Pacific/Guadalcanal",# UTC+11:00
    "Pacific/Auckland"    # UTC+12:00
]
# import pytz
# from datetime import datetime
# for item in timezones:
#     timezone = pytz.timezone(item)
#     now = datetime.now(timezone)
#     utc_offset = now.utcoffset().total_seconds() / 3600  # 偏移量（小时）
#
#     print(item+" : %s"%(utc_offset))

i = 0
while i < len(ids):
    a = "update  u_notification_subscriptions  uns set timezone  =  '%s' where user_id ='%s';"%(timezones[i],ids[i])
    b = "update user_profile up set timezone_id = '%s' where user_id ='%s';"%(timezones[i],ids[i])
    print(a)
    print(b)
    i+=1