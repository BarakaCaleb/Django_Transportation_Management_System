from functools import wraps
from collections import namedtuple
import threading
import logging

from django.utils import timezone


_logger = logging.getLogger(__name__)

ValueAndType = namedtuple("ValueAndType", ["value", "type"])

class ExpireLruCache:

    """ A simple cache decorator with expiration support. In this project, it is used to decorate methods that frequently access the database and do not require real-time data.
    Like functools.lru_cache in the standard library, the decorated function cannot use unhashable parameters.
    The parameter expire_time is the expiration time and must be of type datetime.timedelta. The default is 3 minutes.
    If enable_log is True, a log will be recorded each time the cache is accessed [function name, parameters, cache access count].
    """

    def __init__(self, expire_time=timezone.timedelta(minutes=3), enable_log=False):
        assert isinstance(expire_time, timezone.timedelta), "expire_time parameter must be of type datetime.timedelta"
        self.expire_time = expire_time
        self.enable_log = enable_log
        self._dic = {}
        self._lock = threading.RLock()

    @staticmethod
    def _print_log(func, args, kwargs, count):
        _logger.info("%s: function name: %s, args: (%s), get cache count: %s" % (
            __name__,
            func.__name__,
            ", ".join([*[str(arg) for arg in args], *["%s=%s" % (k, v) for k, v in kwargs]]),
            count,
        ))

    def __call__(self, func):
        @wraps(func)
        def _func(*args, **kwargs):
            # Each parameter of the decorated function must be hashable
            hashable_args = tuple((ValueAndType(value=arg, type=type(arg)) for arg in args))
            hashable_kwargs = frozenset((
                (k, ValueAndType(value=v, type=type(v))) for k, v in kwargs.items()
            ))
            key_ = hash((func, hashable_args, hashable_kwargs))
            with self._lock:
                if key_ in self._dic.keys():
                    if self._dic[key_]["latest_update_time"] + self.expire_time > timezone.now():
                        self._dic[key_]["count"] += 1
                        if self.enable_log:
                            self._print_log(func, args, kwargs, self._dic[key_]["count"])
                        return self._dic[key_]["result"]
            result = func(*args, **kwargs)
            with self._lock:
                self._dic[key_] = {
                    "result": result,
                    "latest_update_time": timezone.now(),
                    "count": 0,
                }
            return result
        return _func

'''
# Function decorator version of ExpireLruCache. The effect is exactly the same as the class decorator version, but the readability is not as good. For reference only.

def ExpireLruCache(expire_time=timezone.timedelta(minutes=3), enable_log=False):

    _dic = {}
    _lock = threading.RLock()

    def _print_log(func, args, kwargs, count):
        _logger.info("%s: function name: %s, args: (%s), get cache count: %s" % (
            __name__,
            func.__name__,
            ", ".join([*[str(arg) for arg in args], *["%s=%s" % (k, v) for k, v in kwargs]]),
            count,
        ))

    def wrapper(func):
        @wraps(func)
        def _func(*args, **kwargs):
            nonlocal _dic
            hashable_args = tuple((ValueAndType(value=arg, type=type(arg)) for arg in args))
            hashable_kwargs = frozenset((
                (k, ValueAndType(value=v, type=type(v))) for k, v in kwargs.items()
            ))
            key_ = hash((func, hashable_args, hashable_kwargs))
            with _lock:
                if key_ in _dic.keys() and _dic[key_]["latest_update_time"] + expire_time > timezone.now():
                    _dic[key_]["count"] += 1
                    if enable_log:
                        _print_log(func, args, kwargs, _dic[key_]["count"])
                    return _dic[key_]["result"]
            result = func(*args, **kwargs)
            with _lock:
                _dic[key_] = {
                    "result": result,
                    "latest_update_time": timezone.now(),
                    "count": 0,
                }
            return result
        return _func

    return wrapper
'''
