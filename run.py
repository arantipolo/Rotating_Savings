from app import create_app, db

app = create_app()

if __name__ == '__main__':
    # Creates local SQLite tables when running the app directly for development
    # Render uses wsgi.py and the pre-deploy init-db command instead
    with app.app_context():
        db.create_all()
        print("Database tables created")

    app.run(debug=True, port=8000)
