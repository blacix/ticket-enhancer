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
from flask import Flask, request, jsonify, render_template_string
from typing import Dict, Any, Optional
from functools import wraps

# Import existing enhancer (assumes it's in the same directory or Python path)
from jira_issue_enhancer import JiraIssueEnhancer, LlamaJiraEnhancer


class JiraConnectApp:
    """Jira Connect App for ticket enhancement"""

    def __init__(self):
        self.app = Flask(__name__)
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

        @self.app.route('/atlassian-connect.json')
        def app_descriptor():
            """Serve the app descriptor for Jira Connect"""
            descriptor = {
                "name": "LLM Ticket Enhancer",
                "description": "Enhance Jira tickets using local LLM",
                "key": "llm-ticket-enhancer",
                "baseUrl": os.getenv('APP_BASE_URL', 'https://your-app-domain.com'),
                "vendor": {
                    "name": "Your Company",
                    "url": "https://your-company.com"
                },
                "authentication": {
                    "type": "jwt"
                },
                "lifecycle": {
                    "installed": "/installed",
                    "uninstalled": "/uninstalled"
                },
                "scopes": [
                    "READ",
                    "WRITE"
                ],
                "modules": {
                    "webPanels": [
                        {
                            "key": "enhancement-panel",
                            "location": "atl.jira.view.issue.right.context",
                            "name": {
                                "value": "LLM Enhancement"
                            },
                            "url": "/panel?issueKey={issue.key}",
                            "conditions": [
                                {
                                    "condition": "user_is_logged_in"
                                }
                            ]
                        }
                    ]
                },
                "apiVersion": 1
            }
            return jsonify(descriptor)

        @self.app.route('/installed', methods=['POST'])
        def installed():
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
        def uninstalled():
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

        @self.app.route('/panel')
        @self.jwt_required
        def enhancement_panel():
            """Serve the enhancement panel UI"""
            issue_key = request.args.get('issueKey')

            # Simple HTML panel with enhancement button
            panel_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>LLM Enhancement</title>
                <script src="https://connect-cdn.atl-paas.net/all.js"></script>
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; }
                    .btn { 
                        background: #0052cc; 
                        color: white; 
                        border: none; 
                        padding: 10px 20px; 
                        cursor: pointer; 
                        border-radius: 4px;
                        margin: 5px;
                    }
                    .btn:hover { background: #0043a6; }
                    .result { margin-top: 20px; padding: 10px; border-radius: 4px; }
                    .success { background: #e6f4ea; border: 1px solid #34a853; }
                    .error { background: #fce8e6; border: 1px solid #ea4335; }
                    .loading { color: #666; }
                </style>
            </head>
            <body>
                <h3>🤖 LLM Ticket Enhancement</h3>
                <p>Issue: <strong>{{ issue_key }}</strong></p>

                <button class="btn" onclick="previewEnhancement()">👁️ Preview Enhancement</button>
                <button class="btn" onclick="applyEnhancement()">✨ Apply Enhancement</button>

                <div id="result"></div>

                <script>
                    function showResult(message, type) {
                        const result = document.getElementById('result');
                        result.className = 'result ' + type;
                        result.innerHTML = message;
                    }

                    function previewEnhancement() {
                        showResult('🔄 Generating preview...', 'loading');

                        AP.request({
                            url: '/api/enhance?action=preview&issueKey={{ issue_key }}',
                            type: 'GET',
                            success: function(data) {
                                const response = JSON.parse(data);
                                if (response.success) {
                                    showResult(
                                        '<h4>Preview:</h4><pre>' + response.enhanced_description + '</pre>',
                                        'success'
                                    );
                                } else {
                                    showResult('❌ Preview failed: ' + response.error, 'error');
                                }
                            },
                            error: function() {
                                showResult('❌ Request failed', 'error');
                            }
                        });
                    }

                    function applyEnhancement() {
                        if (!confirm('Apply enhancement to this ticket?')) return;

                        showResult('🔄 Applying enhancement...', 'loading');

                        AP.request({
                            url: '/api/enhance?action=apply&issueKey={{ issue_key }}',
                            type: 'POST',
                            success: function(data) {
                                const response = JSON.parse(data);
                                if (response.success) {
                                    showResult('✅ Enhancement applied successfully!', 'success');
                                    // Refresh the issue view
                                    AP.jira.refreshIssuePage();
                                } else {
                                    showResult('❌ Enhancement failed: ' + response.error, 'error');
                                }
                            },
                            error: function() {
                                showResult('❌ Request failed', 'error');
                            }
                        });
                    }
                </script>
            </body>
            </html>
            """

            return render_template_string(panel_html, issue_key=issue_key)

        @self.app.route('/api/enhance')
        @self.jwt_required
        def enhance_api():
            """API endpoint for enhancement operations"""
            try:
                action = request.args.get('action', 'preview')
                issue_key = request.args.get('issueKey')
                custom_instructions = request.args.get('instructions', '')

                if not issue_key:
                    return jsonify({'success': False, 'error': 'Issue key required'}), 400

                # Get JWT payload for user context
                jwt_payload = getattr(request, 'jwt_payload', {})
                base_url = jwt_payload.get('iss', '')

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
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/health')
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'installed_tenants': len(self.installed_tenants),
                'timestamp': time.time()
            })

        @self.app.route('/demo')
        def demo():
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

        @self.app.route('/test-auth')
        @self.jwt_required
        def test_auth():
            payload = getattr(request, 'jwt_payload', {})
            return jsonify({
                'authenticated': True,
                'user': payload.get('sub'),
                'tenant': payload.get('iss')
            })

        @self.app.route('/descriptor')
        def serve_file():
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

    def jwt_required(self, f):
        """Decorator to verify JWT tokens from Jira"""

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

    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run the Flask app"""
        print(f"🚀 Starting Jira Connect App on {host}:{port}")
        print(f"📋 App descriptor: http://{host}:{port}/atlassian-connect.json")
        self.app.run(host=host, port=port, debug=debug)


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
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'

    print(f"\n🔗 To install in Jira:")
    print(f"   1. Go to Jira Settings > Apps > Manage Apps")
    print(f"   2. Click 'Upload app'")
    print(f"   3. Enter URL: {os.getenv('APP_BASE_URL')}/atlassian-connect.json")
    print(f"   4. Click 'Upload'")

    connect_app.run(port=port, debug=debug)


if __name__ == "__main__":
    main()
