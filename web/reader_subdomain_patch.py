

# --- Railway patch -------------------------------------------------------
# `get_subdomain` above reads the first label of any host carrying two or more
# dots as a blurblog username. That is right for `newsblur.com` and wrong for
# every Railway hostname: `<service>-production.up.railway.app` has three dots,
# so the index view looks up a user named after the service, finds none, and
# redirects to the site's own root -- an infinite loop on the front page.
#
# Redefining the module global is enough, because `index` resolves it at call
# time. The replacement decides from the configured site domain rather than from
# a dot count, so a real blurblog subdomain still resolves wherever wildcard DNS
# exists, and an exact match on the site domain never does.
_railway_original_get_subdomain = get_subdomain  # noqa: F821


def get_subdomain(request):  # noqa: F811
    host = (request.META.get("HTTP_HOST") or "").split(":")[0]
    if not host:
        return None

    from django.contrib.sites.models import Site

    try:
        site_domain = Site.objects.get_current().domain.split(":")[0]
    except Exception:  # noqa: BLE001
        return _railway_original_get_subdomain(request)

    if not site_domain or host == site_domain:
        return None
    if host.endswith("." + site_domain):
        return host[: -(len(site_domain) + 1)].split(".")[0]
    return _railway_original_get_subdomain(request)
