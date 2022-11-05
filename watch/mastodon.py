from mastodon import Mastodon

def toot(access_token, api_base_url, text):
    mastodon = Mastodon(
        access_token = access_token,
        api_base_url = api_base_url
    )
    mastodon.toot(text[:499])
