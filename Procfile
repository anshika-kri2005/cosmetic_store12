web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn cosmetic_store.wsgi:application --bind 0.0.0.0:${PORT:-8000} --log-file -
