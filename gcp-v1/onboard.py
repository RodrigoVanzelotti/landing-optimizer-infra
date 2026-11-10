"""Generate a customer install snippet. --smoke verifies ingestion and analytics."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from deploy import ACCOUNT, REGION, ROOT, cloud

API = "https://landing-optimizer-api-505424813528.southamerica-east1.run.app"
DEFAULT_DOMAIN = "landing-optimizer-landing-page-505424813528.southamerica-east1.run.app"


def request(path, data=None, token=None, origin=None, method=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(API + path, headers=headers, method=method,
                                 data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=60) as response:
        body = response.read()
        return response.status, json.loads(body) if body else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Bare hostname of the page to track; defaults to the existing Google Cloud landing page")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    domain = args.domain
    if urllib.parse.urlsplit("https://" + domain).netloc != domain or any(c in domain for c in '<>"\' /\\'):
        parser.error("--domain must be a bare hostname")
    password = cloud("secrets", "versions", "access", "1", "--secret=lo-v1-operator-password", capture=True)
    credentials = {"email": ACCOUNT, "password": password}
    try:
        _, auth = request("/v1/auth/login", credentials)
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
        _, auth = request("/v1/auth/register", {**credentials, "tenantName": "Landing Optimizer", "name": "Rodrigo Vanzelotti"})
    token = auth["accessToken"]
    _, sites = request("/v1/sites", token=token)
    site = next((s for s in sites if s["primaryDomain"] == domain), None)
    if site is None:
        _, site = request("/v1/sites", {"name": domain, "primaryDomain": domain}, token)
    site_id = site["id"]
    if domain == DEFAULT_DOMAIN:
        # Cloud Run exposes both project-number and hashed hostname aliases.
        canonical = cloud("run", "services", "describe", "landing-optimizer-landing-page",
                          f"--region={REGION}", "--format=value(status.url)", capture=True)
        _, origins = request(f"/v1/sites/{site_id}/origins", token=token)
        if canonical not in [o["origin"] for o in origins]:
            request(f"/v1/sites/{site_id}/origins", {"origin": canonical}, token)
    _, snippet = request(f"/v1/sites/{site_id}/snippet", token=token)
    (ROOT / "install.html").write_text(snippet["html"] + "\n", encoding="utf-8")
    print(f"Generated install.html for {domain}; site ID: {site_id}")
    if args.smoke:
        origin = "https://" + domain
        for file in ["lo.js", "loader.js", "lo-capture.js"]:
            with urllib.request.urlopen(f"{API}/v1/sdk/v0.1.0/{file}", timeout=60) as response:
                assert response.status == 200 and len(response.read()) > 100
        try:
            request("/v1/sdk/v0.1.0/package.json")
            raise AssertionError("Non-SDK file was served")
        except urllib.error.HTTPError as error:
            assert error.code == 404
        _, config = request(f"/v1/config/{site_id}", origin=origin)
        assert config["siteId"] == site_id and config["sig"]
        _, before = request(f"/v1/analytics/funnel?siteId={site_id}", token=token)
        before_count = next((r["count"] for r in before if r["event"] == "page_view"), 0)
        envelope = {"v": 1, "siteId": site_id, "ik": site["ingestKey"], "sid": "deployment-smoke-test",
                    "sentAt": int(time.time() * 1000), "ctx": {"path": "/__deployment_smoke", "ref": "", "dev": "desktop", "br": "other", "lang": "en"},
                    "events": [{"n": "page_view", "t": 0}, {"n": "hover", "t": 1, "sel": "#hero", "dw": 1000}]}
        assert request("/v1/events", envelope, origin=origin)[0] == 202
        preflight = urllib.request.Request(API + "/v1/events", method="OPTIONS", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        with urllib.request.urlopen(preflight, timeout=60) as response:
            assert response.headers["Access-Control-Allow-Origin"] == origin
        try:
            request("/v1/events", envelope, origin="https://unauthorized.example")
            raise AssertionError("Unauthorized origin was accepted")
        except urllib.error.HTTPError as error:
            assert error.code == 403
        try:
            request("/v1/events", {**envelope, "ik": "invalid-key"}, origin=origin)
            raise AssertionError("Invalid ingest key was accepted")
        except urllib.error.HTTPError as error:
            assert error.code == 403
        try:
            request("/v1/events", {**envelope, "padding": "x" * 33000}, origin=origin)
            raise AssertionError("Oversized event body was accepted")
        except urllib.error.HTTPError as error:
            assert error.code == 413
        _, after = request(f"/v1/analytics/funnel?siteId={site_id}", token=token)
        assert next(r["count"] for r in after if r["event"] == "page_view") >= before_count + 1
        query = urllib.parse.urlencode({"siteId": site_id, "path": "/__deployment_smoke", "from": "2026-01-01", "to": "2099-01-01"})
        _, heatmap = request("/v1/analytics/heatmap?" + query, token=token)
        assert heatmap["pageViews"] >= 1 and heatmap["elements"][0]["hoverMs"] >= 1000
        _, overview = request(f"/v1/analytics/overview?siteId={site_id}", token=token)
        assert overview["pageViews"] >= 1
        assert request(f"/v1/analytics/sections?siteId={site_id}", token=token)[0] == 200
        (ROOT / "smoke-result.json").write_text(json.dumps({"siteId": site_id, "domain": domain, "api": API, "funnel": after, "heatmap": heatmap}, indent=2) + "\n")
        print("Smoke passed: SDK, signed config, stored events, analytics, and origin rejection.")


if __name__ == "__main__":
    main()
