from mastodon import Mastodon

output = Mastodon.create_app(
    "MyMastodonApp",
    api_base_url="https://social-sandbox.com",
    scopes=["read", "write", "follow"],
    to_file="clientcred.secret",
)
print(type(output))
print(output)
