from openai import OpenAI

XAI_API_KEY = "xai-bDQHyZKnMNcSnDz2ARt0FF5kCEahZd40JYEls5Ty3NCJp4G1mjEWf1WK5GmhGnP3qrGuUK7rpifqZGVX"
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)