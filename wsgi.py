from app import create_app

# Production entry point used by Render and gunicorn
# Keeps deployment startup separate from the local run.py development server
app = create_app()
