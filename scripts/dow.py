import datetime, sys
print(datetime.date.fromisoformat(sys.argv[1]).isoweekday())
