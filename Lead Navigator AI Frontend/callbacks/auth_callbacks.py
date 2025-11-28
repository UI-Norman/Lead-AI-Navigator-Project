from dash import Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import requests
from dash import html
import logging
import jwt
from dotenv import load_dotenv
from urllib.parse import parse_qs, urlparse
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Use environment variable or fallback
import os
load_dotenv(dotenv_path=".env")

# Get API URL from environment
API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    raise EnvironmentError("API_BASE_URL is required in .env file")

def register_auth_callbacks(app):
    """Register all authentication-related callbacks"""

    @app.callback(
        [Output('auth-token', 'data', allow_duplicate=True),           # ← ADD THIS
        Output('login-feedback', 'children', allow_duplicate=True),  # ← ADD THIS
        Output('url', 'pathname', allow_duplicate=True)],
        [Input('login-button', 'n_clicks')],
        [State('login-email', 'value'),
        State('login-password', 'value')],
        prevent_initial_call=True
    )
    def login(n_clicks, email, password):
        """Handle user login with detailed error handling"""
        if not n_clicks or not email or not password:
            return no_update, "", no_update

        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                data={"username": email, "password": password},
                timeout=50
            )

            logger.debug(f"Login response: {response.status_code} - {response.text[:100]}")

            if response.status_code == 200:
                data = response.json()
                if 'access_token' in data:
                    token = data['access_token']
                    try:
                        decoded_token = jwt.decode(token, options={"verify_signature": False})
                        logger.debug(f"Login token: sub={decoded_token.get('sub')}, exp={decoded_token.get('exp')}")
                    except Exception as e:
                        logger.warning(f"Failed to decode login token: {str(e)}")
                    success_msg = dbc.Alert("Login successful! Redirecting...", color="success", dismissable=True)
                    return token, success_msg, "/"
                else:
                    no_token_msg = dbc.Alert("Login succeeded but no token received. Contact support.", color="warning")
                    return None, no_token_msg, no_update
            else:
                try:
                    error_data = response.json()
                    detail = error_data.get('detail', 'Unknown error')
                    if 'user not found' in detail.lower() or 'email' in detail.lower():
                        specific_msg = dbc.Alert([
                            html.H5("User Not Found", className="alert-heading"),
                            html.P(f"Email {email} not registered. Please create an account."),
                            dbc.Button("Go to Register", href="/register", color="primary", className="mt-2")
                        ], color="danger")
                    else:
                        specific_msg = dbc.Alert(f"Login failed: {detail} (Status: {response.status_code}). Try again.", color="danger")
                except:
                    specific_msg = dbc.Alert(f"Login failed (Status: {response.status_code}). Check connection.", color="danger")

                logger.error(f"Login failed for {email}: {response.status_code} - {response.text}")
                return None, specific_msg, no_update
        except requests.exceptions.Timeout:
            timeout_msg = dbc.Alert("Login timed out. Check if backend is running.", color="danger")
            return None, timeout_msg, no_update
        except Exception as e:
            error_msg = dbc.Alert(f"Connection error: {str(e)}", color="danger")
            logger.error(f"Login connection error: {str(e)}")
            return None, error_msg, no_update

    @app.callback(
        [Output('register-feedback', 'children'),
         Output('url', 'pathname', allow_duplicate=True)],
        [Input('register-button', 'n_clicks')],
        [State('register-name', 'value'),
         State('register-email', 'value'),
         State('register-password', 'value')],
        prevent_initial_call=True
    )
    def register(n_clicks, name, email, password):
        """Handle user registration with detailed error handling"""
        if not n_clicks or not name or not email or not password:
            return "", no_update

        if len(password) < 8:
            weak_msg = dbc.Alert("Password must be at least 8 characters.", color="warning")
            return weak_msg, no_update

        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/register",
                json={"full_name": name, "email": email, "password": password},
                timeout=50
            )

            logger.debug(f"Register response: {response.status_code} - {response.text[:100]}")

            if response.status_code in [200, 201]:
                success_msg = dbc.Alert("Account created! Redirecting to login...", color="success", dismissable=True)
                return success_msg, "/"
            else:
                try:
                    error_data = response.json()
                    detail = error_data.get('detail', 'Registration failed')
                    if 'already exists' in detail.lower() or 'email' in detail.lower():
                        specific_msg = dbc.Alert([
                            html.H5("Email Already Registered", className="alert-heading"),
                            html.P(f"Email {email} already registered. Try logging in."),
                            dbc.Button("Go to Login", href="/", color="primary", className="mt-2")
                        ], color="danger")
                    else:
                        specific_msg = dbc.Alert(f"Registration failed: {detail} (Status: {response.status_code})", color="danger")
                except:
                    specific_msg = dbc.Alert(f"Registration failed (Status: {response.status_code}).", color="danger")

                logger.error(f"Register failed for {email}: {response.status_code} - {response.text}")
                return specific_msg, no_update
        except requests.exceptions.Timeout:
            timeout_msg = dbc.Alert("Registration timed out. Check if backend is running.", color="danger")
            return timeout_msg, no_update
        except Exception as e:
            error_msg = dbc.Alert(f"Connection error: {str(e)}", color="danger")
            logger.error(f"Register connection error: {str(e)}")
            return error_msg, no_update

    @app.callback(
        [Output('magic-link-feedback', 'children'),
        Output('auth-token', 'data', allow_duplicate=True),  # ADD THIS
        Output('url', 'pathname', allow_duplicate=True)],   # ADD THIS
        Input('magic-link-button', 'n_clicks'),
        State('login-email', 'value'),
        prevent_initial_call=True
    )
    def request_magic_link(n_clicks, email):
        if not n_clicks or not email:
            return no_update, no_update, no_update

        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/magic-link",
                data={"email": email},
                timeout=50
            )

            if response.status_code == 200:
                data = response.json()
                magic_link = data.get('magic_link', '')
                access_token = data.get('access_token')  # GET TOKEN

                if access_token:
                    # AUTO LOGIN WITHOUT CLICKING LINK
                    return (
                        dbc.Alert([
                            html.Strong("Logged in instantly! "),
                            html.A("Click here if not redirected", href=magic_link, target="_blank")
                        ], color="success", dismissable=True),
                        access_token,
                        "/"  # Redirect to dashboard
                    )

                # Fallback: show link
                return (
                    dbc.Alert([
                        html.Strong("Magic Link Sent! "),
                        html.A("Click here to login", href=magic_link, target="_blank")
                    ], color="success", dismissable=True),
                    no_update,
                    no_update
                )

            else:
                err = response.json().get('detail', 'Unknown error')
                return dbc.Alert(f"Error: {err}", color="danger"), no_update, no_update

        except Exception as e:
            logger.error(f"Magic link error: {e}")
            return dbc.Alert("Connection error", color="danger"), no_update, no_update
    # @app.callback(
    # [Output('auth-token', 'data', allow_duplicate=True),           
    #  Output('url', 'pathname', allow_duplicate=True),            
    #  Output('login-feedback', 'children', allow_duplicate=True)],
    # [Input('url', 'pathname'),
    #  Input('url', 'search')],
    # [State('auth-token', 'data')],
    # prevent_initial_call=True
    # )
    # def handle_magic_link_redirect(pathname, search, existing_token):
    #     if not pathname.startswith('/auth/verify'):
    #         return no_update, no_update, no_update

    #     query_params = parse_qs(urlparse(search).query)
    #     magic_token = query_params.get('token', [None])[0]

    #     if not magic_token:
    #         error = dbc.Alert("Invalid magic link", color="danger")
    #         return no_update, no_update, error

    #     try:
    #         resp = requests.get(
    #             f"{API_BASE_URL}/auth/verify-magic-link?token={magic_token}",
    #             timeout=50
    #         )

    #         if resp.status_code != 200:
    #             try:
    #                 err = resp.json().get('detail', 'Invalid or expired link')
    #             except:
    #                 err = "Verification failed"
    #             return no_update, no_update, dbc.Alert(err, color="danger")

    #         data = resp.json()
    #         access_token = data.get('access_token')
    #         if not access_token:
    #             return no_update, no_update, dbc.Alert("No access token received", color="danger")

    #         logger.info(f"Magic link verified → Auto login for {data.get('user', {}).get('email')}")
    #         return (
    #             access_token,
    #             "/",
    #             dbc.Alert("Logged in successfully via magic link!", color="success", dismissable=True)
    #         )

    #     except Exception as e:
    #         logger.error(f"Magic link verify error: {e}")
    #         return no_update, no_update, dbc.Alert(f"Error: {str(e)}", color="danger")
    @app.callback(
        Output('current-user', 'data'),
        Input('auth-token', 'data')
    )
    def load_current_user(token):
        if not token:
            return None
        try:
            resp = requests.get(f"{API_BASE_URL}/users/me?token={token}", timeout=50)
            return resp.json() if resp.status_code == 200 else None
        except:
            return None

    @app.callback(
        [Output('auth-token', 'data', allow_duplicate=True),
         Output('url', 'pathname', allow_duplicate=True)],
        Input('logout', 'n_clicks'),
        prevent_initial_call=True
    )
    def logout(n_clicks):
        if n_clicks:
            return None, "/"
        return no_update, no_update