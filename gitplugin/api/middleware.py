"""
Middleware components for Git Plugin API

Provides logging, metrics collection, and other cross-cutting concerns.
"""

import time
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram, Gauge
import uuid


# Prometheus metrics
request_count = Counter(
    'gitplugin_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code']
)

request_duration = Histogram(
    'gitplugin_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

active_requests = Gauge(
    'gitplugin_active_requests',
    'Number of active HTTP requests'
)

# Configure logger
logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request/response logging middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging"""
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request start
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        logger.info(
            f"Request started - ID: {request_id} - "
            f"Method: {request.method} - "
            f"URL: {request.url} - "
            f"Client IP: {client_ip} - "
            f"User Agent: {user_agent}"
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log response
            duration = time.time() - start_time
            logger.info(
                f"Request completed - ID: {request_id} - "
                f"Status: {response.status_code} - "
                f"Duration: {duration:.3f}s"
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed - ID: {request_id} - "
                f"Error: {str(e)} - "
                f"Duration: {duration:.3f}s",
                exc_info=True
            )
            raise


class MetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus metrics collection middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with metrics collection"""
        # Extract method and endpoint
        method = request.method
        endpoint = self._get_endpoint_pattern(request)
        
        # Increment active requests
        active_requests.inc()
        
        # Start timing
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            status_code = str(response.status_code)
            
            request_count.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            request_duration.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            return response
            
        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time
            
            request_count.labels(
                method=method,
                endpoint=endpoint,
                status_code="500"
            ).inc()
            
            request_duration.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            raise
            
        finally:
            # Decrement active requests
            active_requests.dec()
    
    def _get_endpoint_pattern(self, request: Request) -> str:
        """Extract endpoint pattern from request"""
        path = request.url.path
        
        # Map common patterns to reduce cardinality
        if path.startswith("/api/v1/auth"):
            return "/api/v1/auth/*"
        elif path.startswith("/api/v1/credentials"):
            return "/api/v1/credentials/*"
        elif path.startswith("/api/v1/repositories"):
            return "/api/v1/repositories/*"
        elif path.startswith("/api/v1/webhooks"):
            return "/api/v1/webhooks/*"
        elif path.startswith("/api/v1/jobs"):
            return "/api/v1/jobs/*"
        elif path.startswith("/api/v1/health"):
            return "/api/v1/health/*"
        elif path == "/health":
            return "/health"
        elif path == "/metrics":
            return "/metrics"
        elif path == "/":
            return "/"
        else:
            return "/unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers"""
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_times = {}  # client_ip -> list of request times
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting"""
        client_ip = request.client.host if request.client else "unknown"
        
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        current_time = time.time()
        
        # Clean up old request times (older than 1 minute)
        if client_ip in self.request_times:
            self.request_times[client_ip] = [
                req_time for req_time in self.request_times[client_ip]
                if current_time - req_time < 60
            ]
        else:
            self.request_times[client_ip] = []
        
        # Check rate limit
        if len(self.request_times[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for client: {client_ip}")
            return Response(
                content='{"error": "Rate limit exceeded"}',
                status_code=429,
                headers={"Content-Type": "application/json"}
            )
        
        # Record this request
        self.request_times[client_ip].append(current_time)
        
        # Process request
        return await call_next(request)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle errors globally"""
        try:
            return await call_next(request)
        except Exception as e:
            logger.error(f"Unhandled error in request: {e}", exc_info=True)
            
            # Return generic error response
            return Response(
                content='{"error": "Internal server error"}',
                status_code=500,
                headers={"Content-Type": "application/json"}
            ) 