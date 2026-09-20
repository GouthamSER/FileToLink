import time

StartTime = time.time()
__version__ = 1.1

# Convenience re-exports so both 'from lib import File2Link' and 'from lib.bot import File2Link' work seamlessly
from lib.bot import File2Link, multi_clients, work_loads
