"""Authentication module for quickScheduler frontend.

This module provides user authentication, session management,
and password encryption functionality.
"""

import logging
import bcrypt
import hashlib
import secrets
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config, instance=None):
        super().__init__(app)
        self.config = config
        
        # If an instance is provided, use its sessions dictionary
        if instance:
            self.sessions = instance.sessions
            self.username = instance.username
            self.password = instance.password
        else:
            self.sessions = {}
            # Initialize user credentials from config
            self.username = self.config.get("auth_username", "admin")
            self.password = self.config.get("auth_password", "admin")
            if self.username and self.password:
                # Hash password if it's not already hashed
                if not len(self.password) == 64:
                    self.password = hashlib.sha256(self.password.encode()).hexdigest()
                    print("="*50)
                    print("***\n"*5)
                    print("WARNING: Password is not hashed. Replace the auth_password in your config file with:")
                    print(f"auth_password: {self.password}\n")
                    print("***\n"*5)
                    print("="*50)
            logging.info(f"username={self.username}, password={self.password}")
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Exclude login page and login endpoint from authentication
        if request.url.path == "/login" or request.url.path.startswith("/static/"):
            return await call_next(request)
        
        # Check session token
        session_token = request.cookies.get("session")
        logging.info(f"Session token: {session_token}, Valid sessions: {list(self.sessions.keys())}")
        
        if not session_token or session_token not in self.sessions:
            logging.info(f"Invalid session, redirecting to login")
            return RedirectResponse("/login")
        
        # Valid session, proceed with request
        logging.info(f"Valid session for path: {request.url.path}")
        return await call_next(request)
    
    def verify_password(self, password: str) -> bool:
        logging.info(f"verify_password : password={password}")
        stored_hash = self.password
        if not stored_hash:
            return False
        # Compare SHA-256 hashes
        if len(password) == 64:  # SHA-256 hash is 64 characters long
            return password.lower() == stored_hash.lower()
        return False
    
    def create_session(self) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = True
        return token
    
    def validate_credentials(self, username: str, password: str) -> Optional[str]:
        logging.info(f"validate : username={username}")
        
        # Check if the username matches
        if username != self.username:
            return None
        
        logging.info(f"validate: password={password}")

        # Get stored password hash
        stored_password = self.password
        
        # Compare SHA-256 hashes
        if len(password) == 64:  # SHA-256 hash is 64 characters long
            # Compare hashes
            if password.lower() == stored_password.lower():
                return self.create_session()
        else:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            if hashed_password == stored_password:
                return self.create_session()
        
        return None