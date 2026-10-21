"""Devin v3 organization API adapter; never inferred from agent prose."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(Exception):
    pass


def mode():
    value = os.getenv("FINCORP_MODE", "manual")
    if value not in ("manual", "sample", "live"):
        raise ProviderError("FINCORP_MODE must be manual, sample, or live")
    return value


class Devin:
    def __init__(self):
        org = os.getenv("DEVIN_ORG_ID", "")
        key = os.getenv("DEVIN_API_KEY", "")
        if not org.startswith("org-") or not key.startswith("cog_"):
            raise ProviderError("Live mode requires DEVIN_ORG_ID and a scoped DEVIN_API_KEY (cog_).")
        self.root = f"https://api.devin.ai/v3/organizations/{urllib.parse.quote(org)}/sessions"
        self.key = key

    def request(self, method, path="", data=None):
        url = self.root + path
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Devin API HTTP {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(f"Devin API transport failure: {type(exc).__name__}") from exc

    def create(self, prompt, title, repo, tag):
        # No bypass_approval or secret_ids; repo access and org policy must already be configured.
        return self.request("POST", data={"prompt": prompt, "title": title, "repos": [repo], "resumable": True, "tags": [tag]})

    def status(self, session_id):
        return self.request("GET", "/" + urllib.parse.quote(session_id))

    def messages(self, session_id, after=""):
        path = "/" + urllib.parse.quote(session_id) + "/messages?first=100"
        if after:
            path += "&after=" + urllib.parse.quote(after)
        return self.request("GET", path)

    def send(self, session_id, message):
        return self.request("POST", "/" + urllib.parse.quote(session_id) + "/messages", {"message": message})
