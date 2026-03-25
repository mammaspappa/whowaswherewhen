import os
import click
from flask import Flask, redirect


def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config.from_mapping(
        DATABASE=os.path.join(app.root_path, 'data', 'wwww.db'),
    )

    # Ensure data directory exists
    os.makedirs(os.path.join(app.root_path, 'data'), exist_ok=True)

    # Database lifecycle
    from db import close_db
    app.teardown_appcontext(close_db)

    # Register routes
    from routes import register_blueprints
    register_blueprints(app)

    # Root redirect
    @app.route('/')
    def index():
        return redirect('/static/index.html')

    # CLI commands
    @app.cli.command('init-db')
    def init_db_command():
        """Create database tables."""
        from db import init_db
        with app.app_context():
            init_db()
        click.echo('Database initialized.')

    @app.cli.command('seed')
    def seed_command():
        """Seed database with sample data."""
        from db.seed import seed
        with app.app_context():
            seed()

    return app
