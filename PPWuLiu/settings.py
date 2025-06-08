# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Create the path for logs
LOG_PATH = os.path.join(BASE_DIR, "logs")
if not os.path.isdir(LOG_PATH):
    if os.path.isfile(LOG_PATH):
        os.remove(LOG_PATH)
    os.makedirs(LOG_PATH)

# Enable Django Debug Toolbar
ENABLE_DJANGO_TOOLBAR = False

# Pyinstrument, temporarily not used, because Django Debug Toolbar is better and more powerful

# Django Debug Toolbar
    # debug_toolbar depends on django.contrib.staticfiles

# Custom

CACHES = {
    'default': {
        # Cache based on local memory
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Expire session immediately when browser is closed

# channels related configuration, temporarily not used
