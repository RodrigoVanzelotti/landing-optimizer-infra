"""Build a checked main commit and serialize releases into the shared Terraform state."""
import contextlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

from deploy import ROOT, WORKSPACE, PROJECT, REGION, TF, apply, cloud, run

OWNER = "RodrigoVanzelotti"
COMPONENTS = {"ai", "api", "dashboard"}
BUCKET = "landing-optimizer-v1-tfstate-505424813528"
LOCK_NAME = "landing-optimizer/v1/deployment.lock"
LOCK_URL = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{urllib.parse.quote(LOCK_NAME, safe='')}"


def google_request(url, method="GET", data=None):
    token = cloud("auth", "print-access-token", capture=True)
    req = urllib.request.Request(url, method=method, data=data, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else {}


def github_request(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "landing-optimizer-deploy"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    req = urllib.request.Request("https://api.github.com/" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def owner_finished(owner):
    repository = owner["repository"]
    if repository not in {f"{OWNER}/landing-optimizer-{c}" for c in COMPONENTS}:
        raise RuntimeError("Deployment lock has an unknown owner; inspect it before unlocking")
    run_id = int(owner["run_id"])
    status = github_request(f"repos/{repository}/actions/runs/{run_id}")
    return status["status"] == "completed" or status.get("run_attempt", 1) > int(owner["attempt"])


@contextlib.contextmanager
def deployment_lock(owner):
    upload = (f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o?uploadType=media"
              f"&name={urllib.parse.quote(LOCK_NAME, safe='')}&ifGenerationMatch=0")
    deadline = time.monotonic() + 1200
    next_owner_check = 0
    while True:
        try:
            acquired = google_request(upload, "POST", json.dumps(owner).encode())
            break
        except urllib.error.HTTPError as error:
            if error.code != 412:
                raise
        if time.monotonic() >= deadline:
            raise TimeoutError("Another deployment holds the shared release lock")
        if time.monotonic() >= next_owner_check:
            try:
                metadata = google_request(LOCK_URL)
                generation = metadata["generation"]
                previous = google_request(LOCK_URL + f"?alt=media&generation={generation}")
                if owner_finished(previous):
                    google_request(LOCK_URL + f"?ifGenerationMatch={generation}", "DELETE")
                    continue
            except urllib.error.HTTPError as error:
                if error.code not in (404, 412):
                    raise
            next_owner_check = time.monotonic() + 60
        print("Waiting for the other repository's deployment...", flush=True)
        time.sleep(10)
    try:
        yield
    finally:
        google_request(LOCK_URL + f"?ifGenerationMatch={acquired['generation']}", "DELETE")


def deployed_images(state):
    release = {"deploy_api": True, "ai_image": None}
    variables = {"module.api[0]": "image", "module.dashboard[0]": "dashboard_image", "module.ai[0]": "ai_image"}
    for resource in state.get("resources", []):
        variable = variables.get(resource.get("module"))
        if resource["type"] == "google_cloud_run_v2_service" and variable:
            release[variable] = resource["instances"][0]["attributes"]["template"][0]["containers"][0]["image"]
    if not release.get("image") or not release.get("dashboard_image"):
        raise RuntimeError("Existing API/dashboard images are missing from Terraform state")
    return release


def build(component, sha):
    context = ROOT / ".build" / f"{component}-{sha}"
    context.mkdir(parents=True)
    repositories = [(component, "")] if component != "api" else [("api", "api"), ("snippet", "snippet")]
    for name, destination in repositories:
        source = WORKSPACE / f"landing-optimizer-{name}"
        target = context / destination
        target.mkdir(parents=True, exist_ok=True)
        for directory in ["src", "app", "test", "tests", "prisma", "public"]:
            if (source / directory).exists():
                shutil.copytree(source / directory, target / directory)
        for pattern in ["package*.json", "tsconfig*.json", "nest-cli.json", "vitest.config.ts", "tsup.config.ts",
                        "next-env.d.ts", "next.config.mjs", "postcss.config.mjs", "tailwind.config.ts",
                        "requirements.txt", "pyproject.toml", "logging.json", "Dockerfile", ".dockerignore", ".eslintrc.json"]:
            for file in source.glob(pattern):
                shutil.copy2(file, target / file.name)
    if component == "api":
        shutil.copy2(ROOT / "Dockerfile", context / "Dockerfile")
    tag = f"{REGION}-docker.pkg.dev/{PROJECT}/landing-optimizer-v1/{component}:{sha}-{os.environ['GITHUB_RUN_ID']}"
    args = ["docker", "build", "-t", tag]
    if component == "dashboard":
        args += ["--build-arg", "API_URL=https://landing-optimizer-api-505424813528.southamerica-east1.run.app/v1"]
    run([*args, context])
    run(["docker", "push", tag])
    digest = cloud("artifacts", "docker", "images", "describe", tag, "--format=value(image_summary.digest)", capture=True)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise RuntimeError("Artifact Registry did not return an immutable image digest")
    return tag.split(":")[0] + "@" + digest


def main():
    os.chdir(ROOT)
    component = os.environ["COMPONENT"]
    sha = os.environ["GITHUB_SHA"]
    repository = os.environ["GITHUB_REPOSITORY"]
    if component not in COMPONENTS or repository != f"{OWNER}/landing-optimizer-{component}" or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Invalid deployment source")
    if github_request(f"repos/{repository}/commits/main")["sha"] != sha:
        print("Skipped: a newer main commit superseded this build")
        return
    run([TF, "init", "-input=false"])
    run([TF, "validate"])
    image = build(component, sha)
    owner = {"repository": repository, "run_id": os.environ["GITHUB_RUN_ID"], "attempt": os.environ["GITHUB_RUN_ATTEMPT"]}
    with deployment_lock(owner):
        if github_request(f"repos/{repository}/commits/main")["sha"] != sha:
            print("Skipped: a newer main commit superseded this deployment")
            return
        release = deployed_images(json.loads(run([TF, "state", "pull"], capture=True)))
        release[{"api": "image", "ai": "ai_image", "dashboard": "dashboard_image"}[component]] = image
        (ROOT / "release.auto.tfvars.json").write_text(json.dumps(release, indent=2) + "\n")
        if component == "api":
            apply("google_cloud_run_v2_job.migrate")
            cloud("run", "jobs", "execute", "landing-optimizer-migrate-v1", f"--region={REGION}", "--wait")
        apply()
        path = "/login" if component == "dashboard" else "/health"
        url = f"https://landing-optimizer-{component}-505424813528.{REGION}.run.app{path}"
        with urllib.request.urlopen(url, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError("Deployment health check failed")
        print(f"Deployed {component}: {sha} -> {image}")
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(f"## Deployed {component}\n\nCommit: `{sha}`\n\nImage: `{image}`\n\nURL: {url}\n")


if __name__ == "__main__":
    main()
