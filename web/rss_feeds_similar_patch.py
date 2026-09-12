

# --- Railway patch -------------------------------------------------------
# `setup_feed_for_premium_subscribers` calls `count_similar_feeds` on every new
# subscription, and that path always reaches OpenAI embeddings. With no key
# configured the exception escapes `add_url`, so subscribing answers 500 *after*
# the subscription row has already been written -- the feed appears on the next
# page load and the UI reports a failure.
#
# A template has to deploy with no third-party keys at all, so the similar-feed
# recommendation degrades to "no recommendations" instead. Set OPENAI_API_KEY to
# a real key and the original behaviour returns with no further change.
_railway_original_count_similar_feeds = Feed.count_similar_feeds  # noqa: F821


def _railway_count_similar_feeds(self, *args, **kwargs):
    key = getattr(settings, "OPENAI_API_KEY", "") or ""  # noqa: F821
    if not key or "XXX" in key:
        return []
    try:
        return _railway_original_count_similar_feeds(self, *args, **kwargs)
    except Exception:  # noqa: BLE001
        logging.debug(" ---> ~FRSimilar-feed recommendations unavailable, skipping")  # noqa: F821
        return []


Feed.count_similar_feeds = _railway_count_similar_feeds  # noqa: F821
