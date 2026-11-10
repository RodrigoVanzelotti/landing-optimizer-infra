"""Deploy V1 with the vendored personal-cloud-infrastructure modules.

Run from this directory: python deploy.py
Requires gcloud, Terraform (PATH or tools/terraform.exe), Python and cloud access.
Secret values are sent to gcloud over stdin and never written to Terraform state.
"""
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent.parent
PROJECT = "landing-optimizer-landing-page"
ACCOUNT = "rodrigovanzelotti@gmail.com"
REGION = "southamerica-east1"
GCLOUD = shutil.which("gcloud.cmd") or shutil.which("gcloud")
TF = shutil.which("terraform") or str(ROOT / "tools/terraform.exe")


def run(args, *, capture=False, data=None):
    result = subprocess.run([str(a) for a in args], cwd=ROOT, input=data, text=True,
                            stdout=subprocess.PIPE if capture else None, check=True)
    return result.stdout.strip() if capture else None


def cloud(*args, capture=False, data=None):
    identity = [] if os.environ.get("GITHUB_ACTIONS") == "true" else [f"--account={ACCOUNT}"]
    return run([GCLOUD, *args, f"--project={PROJECT}", *identity, "--quiet"],
               capture=capture, data=data)


def apply(*targets):
    os.environ["GOOGLE_OAUTH_ACCESS_TOKEN"] = cloud("auth", "print-access-token", capture=True)
    run([TF, "plan", "-input=false", "-lock-timeout=5m", "-out=release.tfplan", *[f"-target={t}" for t in targets]])
    plan = json.loads(run([TF, "show", "-json", "release.tfplan"], capture=True))
    for change in plan.get("resource_changes", []):
        if "delete" in change["change"]["actions"]:
            raise RuntimeError(f"Refusing deletion/replacement: {change['address']}")
    run([TF, "apply", "-input=false", "release.tfplan"])


def secret(name, value):
    versions = json.loads(cloud("secrets", "versions", "list", name, "--format=json", capture=True))
    if versions:
        return cloud("secrets", "versions", "access", "1", f"--secret={name}", capture=True)
    cloud("secrets", "versions", "add", name, "--data-file=-", data=value)
    return value


def build():
    context = ROOT / ".build" / time.strftime("%Y%m%d%H%M%S")
    for source, dest in [("landing-optimizer-api", "api"), ("landing-optimizer-snippet", "snippet")]:
        src = WORKSPACE / source
        out = context / dest
        out.mkdir(parents=True)
        for directory in ["src", "test", "prisma"]:
            if (src / directory).exists():
                shutil.copytree(src / directory, out / directory)
        for pattern in ["package*.json", "tsconfig*.json", "nest-cli.json", "vitest.config.ts", "tsup.config.ts"]:
            for path in src.glob(pattern):
                shutil.copy2(path, out / path.name)
    shutil.copy2(ROOT / "Dockerfile", context / "Dockerfile")
    tag = f"{REGION}-docker.pkg.dev/{PROJECT}/landing-optimizer-v1/api:{context.name}"
    build_id = cloud("builds", "submit", str(context), f"--tag={tag}", "--async", "--format=value(id)", capture=True)
    print(f"Cloud Build: {build_id}", flush=True)
    while True:
        result = json.loads(cloud("builds", "describe", build_id, "--format=json", capture=True))
        status = result["status"]
        if status == "SUCCESS":
            return tag.split(":")[0] + "@" + result["results"]["images"][0]["digest"]
        if status not in ["QUEUED", "WORKING", "PENDING"]:
            raise RuntimeError(f"Cloud Build {build_id}: {status}. Inspect gcloud builds log {build_id}")
        time.sleep(10)


def main():
    os.chdir(ROOT)
    if (ROOT / "tools/terraform.rc").exists():
        os.environ["TF_CLI_CONFIG_FILE"] = str(ROOT / "tools/terraform.rc")
    os.environ["GOOGLE_OAUTH_ACCESS_TOKEN"] = cloud("auth", "print-access-token", capture=True)
    if not (ROOT / ".terraform/terraform.tfstate").exists():
        run([TF, "init", "-input=false"])
    run([TF, "validate"])
    apply("google_service_account.api", "google_project_iam_member.sql_client", "module.artifacts",
          "module.secrets", "google_secret_manager_secret_iam_member.api", "google_sql_database.app")
    database_url = secret("lo-v1-database-url", "postgresql://lo_app:" + secrets.token_hex(24) +
                          f"@localhost/landing_optimizer?host=/cloudsql/{PROJECT}:{REGION}:landing-optimizer-v1&connection_limit=3")
    users = json.loads(cloud("sql", "users", "list", "--instance=landing-optimizer-v1", "--format=json", capture=True))
    if not any(u["name"] == "lo_app" for u in users):
        # Keep the database password out of process arguments and exception messages.
        token = cloud("auth", "print-access-token", capture=True)
        req = urllib.request.Request(
            f"https://sqladmin.googleapis.com/sql/v1beta4/projects/{PROJECT}/instances/landing-optimizer-v1/users",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            data=json.dumps({"name": "lo_app", "password": urllib.parse.urlsplit(database_url).password}).encode())
        with urllib.request.urlopen(req, timeout=60) as response:
            operation = json.load(response)["name"]
        cloud("sql", "operations", "wait", operation, "--timeout=300")
    secret("lo-v1-jwt-secret", secrets.token_hex(32))
    secret("lo-v1-config-key", base64.b64encode(secrets.token_bytes(32)).decode())
    secret("lo-v1-operator-password", secrets.token_urlsafe(32))
    secret("lo-v1-ai-token", secrets.token_urlsafe(48))
    image = build()
    release_path = ROOT / "release.auto.tfvars.json"
    release = json.loads(release_path.read_text()) if release_path.exists() else {"deploy_api": False}
    release["image"] = image
    release_path.write_text(json.dumps(release, indent=2) + "\n")
    apply("google_cloud_run_v2_job.migrate")
    cloud("run", "jobs", "execute", "landing-optimizer-migrate-v1", f"--region={REGION}", "--wait")
    release["deploy_api"] = True
    release_path.write_text(json.dumps(release, indent=2) + "\n")
    apply()
    print("API deployed. Run python onboard.py --domain YOUR_HOST to generate the install snippet.")


if __name__ == "__main__":
    main()
