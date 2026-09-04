"""
URL configuration for mercury project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include, re_path
from django.http import HttpResponse
from pathlib import Path

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / 'mercury-frontend' / 'dist'

def _spa_index(request):
    try:
        html = (_FRONTEND_DIR / 'index.html').read_text(encoding='utf-8')
    except FileNotFoundError:
        html = '<h1>Frontend not built. Run: cd mercury-frontend && npm run build</h1>'
    return HttpResponse(html, content_type='text/html; charset=utf-8')

def _favicon(request):
    try:
        svg = (_FRONTEND_DIR / 'favicon.svg').read_bytes()
        return HttpResponse(svg, content_type='image/svg+xml')
    except FileNotFoundError:
        return HttpResponse(status=404)

urlpatterns = [
    path('favicon.svg', _favicon),
    path('api/', include('ceres.urls')),
    # Catch-all: serve Vue SPA for non-API routes
    re_path(r'^(?!api/|static/).*$', _spa_index),
]
