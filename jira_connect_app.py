#!/usr/bin/env python3
"""
Jira Connect App for LLM Ticket Enhancement
Integrates with existing SimpleJiraEnhancer without modifying existing classes
"""


import os
import json
import jwt
import time
import requests
from flask import Flask, request, jsonify, render_template_string, send_file, make_response
from flask_cors import CORS
from typing import Dict, Any, Optional
from functools import wraps

# Import existing enhancer (assumes it's in the same directory or Python path)
from jira_issue_enhancer import JiraIssueEnhancer, LlamaJiraEnhancer


class JiraConnectApp:
    """Jira Connect App for ticket enhancement"""

    DEFAULT_PORT = 443

    def __init__(self):
        self.app = Flask(__name__)

        # app_base_url = os.getenv('APP_BASE_URL', '')
        # jira_server_url = os.getenv('JIRA_SERVER_URL', '')
        #
        # # Build allowed origins list
        # allowed_origins = [
        #     app_base_url,  # Your app domain
        #     jira_server_url,  # Your Jira instance
        # ]

        # VERY PERMISSIVE CORS - Allow everything for development
        CORS(self.app,
             resources={r"/*": {
                 "origins": "*",  # Allow all origins
                 "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                 "allow_headers": "*",  # Allow all headers
                 "expose_headers": "*",  # Expose all headers
                 "supports_credentials": True,
                 "max_age": 3600
             }})

        self.installed_tenants = self.load_tenants()
        self.setup_routes()

    def load_tenants(self):
        try:
            with open('tenants.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_tenants(self):
        with open('tenants.json', 'w') as f:
            json.dump(self.installed_tenants, f)

    def setup_routes(self):
        """Setup all Flask routes"""
        # Handle ALL OPTIONS requests - very permissive
        @self.app.route('/<path:path>', methods=['OPTIONS'])
        @self.app.route('/enhance', methods=['OPTIONS'])
        @self.app.route('/panel', methods=['OPTIONS'])
        @self.app.route('/descriptor', methods=['OPTIONS'])
        def handle_options(path=None):
            """Handle preflight OPTIONS requests"""
            response = make_response('', 200)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
            response.headers['Access-Control-Max-Age'] = '3600'
            return response

        @self.app.route('/')
        def serve_root():
            return ""

        @self.app.route('/descriptor')
        @self.app.route('/atlassian-connect.json')
        def serve_descriptor():
            """Serve the app descriptor from a JSON file on disk"""
            try:
                with open('atlassian-connect.json', 'r') as f:
                    descriptor = json.load(f)
                return jsonify(descriptor)
            except FileNotFoundError:
                return jsonify({'error': 'App descriptor not found'}), 404
            except json.JSONDecodeError as e:
                return jsonify({'error': f'Invalid JSON in descriptor: {str(e)}'}), 500
            except Exception as e:
                return jsonify({'error': f'Failed to load descriptor: {str(e)}'}), 500

        @self.app.route('/favicon.ico')
        def favicon():
            """Serve favicon for Jira app"""
            try:
                return send_file('favicon.ico', mimetype='image/x-icon')
            except FileNotFoundError:
                # If ico file doesn't exist, return a 404 or create a minimal response
                return '', 404

        @self.app.route('/installed', methods=['POST'])
        def serve_installed():
            """Handle app installation"""
            try:
                data = request.get_json()
                client_key = data.get('clientKey')
                shared_secret = data.get('sharedSecret')
                base_url = data.get('baseUrl')

                # Store installation data
                self.installed_tenants[client_key] = {
                    'shared_secret': shared_secret,
                    'base_url': base_url,
                    'installed_at': time.time()
                }
                self.save_tenants()

                print(f"✅ App installed for tenant: {client_key}")
                return '', 204

            except Exception as e:
                print(f"❌ Installation failed: {e}")
                return jsonify({'error': str(e)}), 400

        @self.app.route('/uninstalled', methods=['POST'])
        def serve_uninstalled():
            """Handle app uninstallation"""
            try:
                data = request.get_json()
                client_key = data.get('clientKey')

                if client_key in self.installed_tenants:
                    del self.installed_tenants[client_key]
                    print(f"✅ App uninstalled for tenant: {client_key}")

                return '', 204

            except Exception as e:
                print(f"❌ Uninstallation failed: {e}")
                return jsonify({'error': str(e)}), 400

        @self.app.route('/health')
        def serve_health():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'installed_tenants': len(self.installed_tenants),
                'timestamp': time.time()
            })

        @self.app.route('/panel')
        # @self.jwt_required
        def serve_enhancement_panel():
            """Serve the enhancement panel UI from HTML file"""
            print(f"📋 Panel called")
            issue_key = request.args.get('issueKey')
            print(f"📋 Panel called with issue: {issue_key}")

            # Get app base URL from environment
            app_base_url = os.getenv('APP_BASE_URL', 'https://do.nowtech.cloud')

            try:
                # Read the HTML file
                with open('panel.html', 'r') as f:
                    html_content = f.read()
                # Replace placeholders with actual values
                html_content = html_content.replace('{{ISSUE_KEY}}', issue_key or '')
                html_content = html_content.replace('{{APP_BASE_URL}}', app_base_url)
                return html_content

            except FileNotFoundError:
                return f"""
                <html>
                    <body>
                        <h3>Error: panel.html not found</h3>
                        <p>Please create panel.html in the same directory as your app.</p>
                    </body>
                </html>
                """, 404

        @self.app.route('/enhance')
        # @self.jwt_required
        def serve_enhance():
            """API endpoint for enhancement operations"""
            try:
                action = request.args.get('action', 'preview')
                print(f'serve_enhance - action: {action}')
                issue_key = request.args.get('issueKey')
                custom_instructions = request.args.get('instructions', '')

                if not issue_key:
                    return jsonify({'success': False, 'error': 'Issue key required'}), 400

                # Get JWT payload for user context
                # jwt_payload = getattr(request, 'jwt_payload', {})
                # base_url = jwt_payload.get('iss', '')

                base_url = os.getenv('JIRA_SERVER_URL')
                # Create enhancer instance using service account credentials
                # (In production, you'd store these securely per tenant)
                enhancer = self._create_enhancer_for_tenant(base_url)

                if action == 'preview':
                    # Preview enhancement
                    result = enhancer.enhance_issue_description(issue_key, custom_instructions)
                    return jsonify(result)

                elif action == 'apply':
                    # Apply enhancement
                    success, message = enhancer.enhance_and_update_issue(issue_key, custom_instructions)
                    return jsonify({
                        'success': success,
                        'message': message
                    })

                else:
                    return jsonify({'success': False, 'error': 'Invalid action'}), 400

            except Exception as e:
                print(f'serve_enhance - failed: {e}')
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/demo')
        def serve_demo():
            """Demo endpoint that enhances a specific DIGI ticket"""
            try:
                server_url = os.getenv('JIRA_SERVER_URL')
                enhancer = self._create_enhancer_for_tenant(server_url)

                # Use a specific DIGI ticket for demo
                ticket_key = "DIGI-894"  # Replace with actual ticket key

                # Enhance the ticket
                result = enhancer.enhance_issue_description(ticket_key)

                if result['success']:
                    return jsonify({
                        'success': True,
                        'ticket_key': ticket_key,
                        'enhanced_description': result['enhanced_description']
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': result['error']
                    }), 500

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.after_request
        def after_request(response):
            # VERY PERMISSIVE - Allow everything

            # Remove restrictive headers
            response.headers.pop('X-Frame-Options', None)

            # Allow all origins and methods
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
            response.headers['Access-Control-Expose-Headers'] = '*'
            response.headers['Access-Control-Allow-Credentials'] = 'true'

            # Very permissive CSP
            response.headers['Content-Security-Policy'] = (
                "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
                "frame-ancestors *; "
                "script-src * 'unsafe-inline' 'unsafe-eval'; "
                "style-src * 'unsafe-inline'; "
                "img-src * data: blob:; "
                "connect-src *;"
            )

            # Remove other restrictive headers
            response.headers.pop('X-Content-Type-Options', None)
            response.headers.pop('Strict-Transport-Security', None)
            response.headers.pop('Referrer-Policy', None)

            return response

    def jwt_required(self, f):
        """Decorator to verify JWT tokens from Jira"""
        print('jwt_required')
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                auth_header = request.headers.get('Authorization', '')
                if not auth_header.startswith('JWT '):
                    return jsonify({'error': 'Missing or invalid JWT token'}), 401

                token = auth_header[4:]  # Remove 'JWT ' prefix

                # Decode without verification first to get the issuer
                unverified = jwt.decode(token, options={"verify_signature": False})
                client_key = unverified.get('iss')

                if client_key not in self.installed_tenants:
                    return jsonify({'error': 'App not installed for this tenant'}), 401

                # Verify with the shared secret
                shared_secret = self.installed_tenants[client_key]['shared_secret']
                payload = jwt.decode(token, shared_secret, algorithms=['HS256'])

                # Add payload to request for use in route handlers
                request.jwt_payload = payload

                return f(*args, **kwargs)

            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Invalid token'}), 401
            except Exception as e:
                return jsonify({'error': f'Authentication error: {str(e)}'}), 401

        return decorated_function

    def _create_enhancer_for_tenant(self, base_url: str) -> JiraIssueEnhancer:
        """Create enhancer instance for a specific tenant"""
        # In production, store tenant-specific credentials securely
        # For demo, using environment variables as fallback

        # You could store per-tenant service account credentials
        # during installation and retrieve them here

        server_url = base_url
        username = os.getenv('JIRA_SERVICE_ACCOUNT_EMAIL')
        api_token = os.getenv('JIRA_SERVICE_ACCOUNT_TOKEN')

        if not all([server_url, username, api_token]):
            raise ValueError("Missing Jira credentials for tenant")

        return JiraIssueEnhancer(
            server_url=server_url,
            username=username,
            api_token=api_token
        )

    def run(self, host='0.0.0.0', port=DEFAULT_PORT, debug=True):
        """Run the Flask app"""
        print(f"🚀 Starting Jira Connect App on {host}:{port}")
        print(f"📋 App descriptor: http://{host}:{port}/descriptor")
        ssl_context = (
            'fullchain.pem',
            'privkey.pem'
        )
        self.app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)


def main():
    """Main entry point for the Connect app"""

    print("🤖 LLM Jira Connect App")
    print("=" * 40)

    # Validate environment
    required_env_vars = [
        'APP_BASE_URL',  # Your app's public URL
        'JIRA_SERVICE_ACCOUNT_EMAIL',  # Service account for Jira API calls
        'JIRA_SERVICE_ACCOUNT_TOKEN'  # Service account API token
    ]


    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("\nRequired environment variables:")
        print("• APP_BASE_URL: Your app's public URL (e.g., https://your-app.ngrok.io)")
        print("• JIRA_SERVICE_ACCOUNT_EMAIL: Email for Jira service account")
        print("• JIRA_SERVICE_ACCOUNT_TOKEN: API token for service account")
        return

    # Create and run the app
    connect_app = JiraConnectApp()

    # Get port from environment (useful for cloud deployment)
    port = int(os.getenv('PORT', JiraConnectApp.DEFAULT_PORT))
    debug = os.getenv('FLASK_ENV') == 'development'

    print(f"\n🔗 To install in Jira:")
    print(f"   1. Go to Jira Settings > Apps > Manage Apps")
    print(f"   2. Click 'Upload app'")
    print(f"   3. Enter URL: {os.getenv('APP_BASE_URL')}/descriptor")
    print(f"   4. Click 'Upload'")

    connect_app.run(port=port, debug=debug)


if __name__ == "__main__":
    main()
