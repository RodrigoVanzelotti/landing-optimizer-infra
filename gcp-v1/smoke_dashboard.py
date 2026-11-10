"""Verify HTTPS dashboard login, refresh cookies, data access and logout."""
import http.cookiejar
import json
import urllib.error
import urllib.request

from deploy import ACCOUNT, cloud

URL = "https://landing-optimizer-dashboard-505424813528.southamerica-east1.run.app"


def main():
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(path, data=None, token=None, method=None):
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(URL + path, headers=headers, method=method,
                                     data=json.dumps(data).encode() if data is not None else None)
        return client.open(req, timeout=60)

    with request("/login") as response:
        assert response.status == 200 and b'Sign in' in response.read()
    password = cloud("secrets", "versions", "access", "1", "--secret=lo-v1-operator-password", capture=True)
    with request("/api/auth/login", {"email": ACCOUNT, "password": password}) as response:
        assert response.status == 200
        auth = json.load(response)
        assert auth["accessToken"]
    cookie = next(c for c in jar if c.name == "__Host-lo_refresh")
    assert cookie.secure and cookie.path == "/" and not cookie.domain_specified
    assert cookie.has_nonstandard_attr("HttpOnly")
    assert cookie.get_nonstandard_attr("SameSite") == "Strict"
    with request("/api/auth/refresh", method="POST") as response:
        token = json.load(response)["accessToken"]
    with request("/api/sites", token=token) as response:
        sites = json.load(response)
        assert sites
    site_id = sites[0]["id"]
    with request(f"/api/sites/{site_id}/snippet", token=token) as response:
        snippet = json.load(response)
        assert "https://landing-optimizer-api-" in snippet["html"] and "localhost" not in snippet["html"]
    with request(f"/api/analytics/overview?siteId={site_id}", token=token) as response:
        assert "pageViews" in json.load(response)
    with request("/api/auth/logout", token=token, method="POST") as response:
        assert response.status == 204
    try:
        request("/api/auth/refresh", method="POST")
        raise AssertionError("Logged-out session was refreshed")
    except urllib.error.HTTPError as error:
        assert error.code == 401
    print("Dashboard smoke passed: login, secure HTTP-only cookie, refresh, sites, snippet, analytics and logout.")


if __name__ == "__main__":
    main()
