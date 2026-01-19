import sys
import traceback

try:
    from tests import test_reminder_service_property
    print('Functions:', [x for x in dir(test_reminder_service_property) if x.startswith('test_')])
except Exception as e:
    traceback.print_exc()
