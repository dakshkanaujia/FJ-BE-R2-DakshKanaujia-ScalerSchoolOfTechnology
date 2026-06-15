#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create a superuser on first deploy if credentials are set in env.
# Safe to run on every deploy — skips if a superuser already exists.
if [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
import os
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        os.environ["DJANGO_SUPERUSER_USERNAME"],
        os.environ["DJANGO_SUPERUSER_EMAIL"],
        os.environ["DJANGO_SUPERUSER_PASSWORD"],
    )
    print("Superuser created.")
else:
    print("Superuser already exists, skipping.")
EOF
fi

# Keep the Site record in sync with the Render hostname so Google OAuth works.
python manage.py shell << 'EOF'
from django.contrib.sites.models import Site
import os
hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "localhost")
site, _ = Site.objects.get_or_create(id=1)
site.domain = hostname
site.name = "Finance Tracker"
site.save()
print(f"Site domain set to {hostname}")
EOF
