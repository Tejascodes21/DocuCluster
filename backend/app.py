import os
from pathlib import Path
from flask import Flask, send_from_directory, jsonify
from backend.config import Config
from backend.models.database import init_db
from backend.api.routes_upload import upload_bp
from backend.api.routes_cluster import cluster_bp
from backend.api.routes_dendrogram import dendrogram_bp
from backend.api.routes_export import export_bp
from backend.api.routes_v2 import api_v2_bp
from backend.api.mcp_server import mcp_bp

def create_app(config_class=Config):
    """Flask Application Factory for DocuCluster AI."""
    frontend_dir = Path(__file__).resolve().parent.parent / 'frontend'
    app = Flask(
        __name__,
        static_folder=str(frontend_dir),
        static_url_path=''
    )
    
    # Load configuration & initialize persistence
    app.config.from_object(config_class)
    config_class.init_app(app)
    init_db(config_class.SQLALCHEMY_DATABASE_URI)

    # Register blueprints (v1 + v2 + MCP API endpoints)
    app.register_blueprint(upload_bp)
    app.register_blueprint(cluster_bp)
    app.register_blueprint(dendrogram_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(api_v2_bp)
    app.register_blueprint(mcp_bp)

    # Serve static frontend pages
    @app.route('/')
    def serve_index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/results.html')
    def serve_results():
        return send_from_directory(app.static_folder, 'results.html')

    # Centralized Error Handlers
    @app.errorhandler(400)
    def bad_request_error(error):
        message = getattr(error, 'description', 'Bad Request')
        return jsonify({"error": message}), 400

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({"error": "File exceeds maximum allowed size cap of 5MB"}), 400

    @app.errorhandler(422)
    def unprocessable_entity_error(error):
        message = getattr(error, 'description', 'Unprocessable Entity')
        return jsonify({"error": message}), 422

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({"error": "Internal server error occurred"}), 500

    return app

app = create_app()

if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting DocuCluster AI server on port {port}...")
    serve(app, host='127.0.0.1', port=port)
