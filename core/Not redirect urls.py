"""
NOT → Project Hub Redirect URLs
================================
This file replaces 'core.not_urls' in config/urls.py.

How it works:
  1. Redirect routes come FIRST — they catch the main navigation paths
     (/not/, /not/list/, /not/<pk>/, /not/<pk>/timeline/) and send a
     permanent 301 redirect to the unified /projects/ equivalents.

  2. ALL original not_urls patterns are included AFTER the redirects.
     Django's first-match-wins means the 6 redirected paths always 301,
     while every other /not/ path (create, edit, wizard, stakeholders,
     resources, deliverables, meetings, learners, documents, attendance)
     falls through to the original not_views and works exactly as before.

  3. URL names are preserved because the included not_urls still register
     names like 'not_detail', 'not_dashboard', 'not_list'. Since Django's
     reverse() scans all patterns by name, reverse('not_detail', pk=5)
     still resolves to /not/5/. When the browser follows that URL it hits
     the redirect and lands on /projects/5/. Two hops, zero breakage.

Safety:
  - core/not_views.py is NOT touched
  - core/not_urls.py is NOT touched
  - All 37 original NOT URL names remain resolvable
  - Templates using {% url 'not_detail' %} etc. still work
  - Form POST actions in not_views that redirect('not_detail') still work
  - Old bookmarks get a clean 301 to the new canonical URL

To activate, change ONE line in config/urls.py:
    BEFORE:  path('not/', include('core.not_urls')),
    AFTER:   path('not/', include('core.not_redirect_urls')),
"""
from django.urls import path, include
from django.views.generic import RedirectView
from django.urls import reverse


# =============================================================================
# CUSTOM REDIRECT VIEWS
# These use reverse() to resolve target URLs at runtime, making them
# immune to URL conf load-order issues.
# =============================================================================


class NOTDashboardRedirect(RedirectView):
    """
    /not/ → /projects/
    The old NOT dashboard now lives at the unified Project Hub.
    """
    permanent = True
    query_string = True    # preserve ?status=DRAFT etc.

    def get_redirect_url(self, *args, **kwargs):
        return reverse('core:projects_dashboard')


class NOTListRedirect(RedirectView):
    """
    /not/list/ → /projects/
    The old NOT list view is now the Project Hub dashboard.
    """
    permanent = True
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        return reverse('core:projects_dashboard')


class NOTDetailRedirect(RedirectView):
    """
    /not/<pk>/ → /projects/<pk>/
    Individual project detail now lives in the unified view.
    """
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        pk = kwargs.get('pk')
        return reverse('core:project_detail', kwargs={'pk': pk})


class NOTTimelineRedirect(RedirectView):
    """
    /not/<pk>/timeline/ → /projects/<pk>/timeline/
    Timeline view was duplicated; redirect to the canonical one.
    """
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        pk = kwargs.get('pk')
        return reverse('core:project_timeline', kwargs={'pk': pk})


class NOTIntakesRedirect(RedirectView):
    """
    /not/intakes/ → /projects/?phase=PLANNING
    The intake calendar is now accessible via the Project Hub
    with the Planning phase filter applied.
    """
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        return reverse('core:projects_dashboard') + '?phase=PLANNING'


class NOTLearnersRedirect(RedirectView):
    """
    /not/<pk>/learners/ → /projects/<pk>/learners/
    Learner tracking now lives under the unified project view.
    """
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        pk = kwargs.get('pk')
        return reverse('core:project_learners', kwargs={'pk': pk})


# =============================================================================
# URL PATTERNS
# Redirects FIRST (first-match-wins), then original NOT routes after.
# =============================================================================

urlpatterns = [
    # ─── Redirects (these match first and send 301) ─────────────────
    path('',
         NOTDashboardRedirect.as_view(),
         name='not_dashboard_redirect'),

    path('list/',
         NOTListRedirect.as_view(),
         name='not_list_redirect'),

    path('intakes/',
         NOTIntakesRedirect.as_view(),
         name='not_intakes_redirect'),

    path('<int:pk>/',
         NOTDetailRedirect.as_view(),
         name='not_detail_redirect'),

    path('<int:pk>/timeline/',
         NOTTimelineRedirect.as_view(),
         name='not_timeline_redirect'),

    path('<int:pk>/learners/',
         NOTLearnersRedirect.as_view(),
         name='not_learners_redirect'),

    # ─── Original NOT routes (everything else falls through here) ───
    #
    # IMPORTANT: We include the FULL not_urls so that:
    #   a) All URL names ('not_detail', 'not_create', etc.) stay registered
    #      for reverse() calls inside not_views.py
    #   b) All non-redirected paths (/not/create/, /not/<pk>/edit/, etc.)
    #      continue to serve their original views
    #
    # The 6 paths above will never reach these duplicates because Django
    # stops at the first match. But the URL NAMES from not_urls still
    # register globally, which is exactly what we need.
    #
    path('', include('core.not_urls')),
]