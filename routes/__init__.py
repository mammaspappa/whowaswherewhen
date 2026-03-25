from routes.persons import bp as persons_bp
from routes.whereabouts import bp as whereabouts_bp
from routes.sources import bp as sources_bp
from routes.contributions import bp as contributions_bp
from routes.search import bp as search_bp
from routes.discussions import bp as discussions_bp
from routes.revisions import bp as revisions_bp


def register_blueprints(app):
    app.register_blueprint(persons_bp)
    app.register_blueprint(whereabouts_bp)
    app.register_blueprint(sources_bp)
    app.register_blueprint(contributions_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(discussions_bp)
    app.register_blueprint(revisions_bp)
