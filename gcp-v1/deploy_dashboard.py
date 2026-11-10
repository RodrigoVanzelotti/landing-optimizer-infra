"""Build and deploy the dashboard into the existing V1 Terraform state."""
import json
import os
import shutil
import time

from deploy import ROOT, WORKSPACE, PROJECT, REGION, TF, cloud, run, apply


def main():
    os.chdir(ROOT)
    if (ROOT / "tools/terraform.rc").exists():
        os.environ["TF_CLI_CONFIG_FILE"] = str(ROOT / "tools/terraform.rc")
    os.environ["GOOGLE_OAUTH_ACCESS_TOKEN"] = cloud("auth", "print-access-token", capture=True)
    run([TF, "get"])
    run([TF, "validate"])

    source = WORKSPACE / "landing-optimizer-dashboard"
    context = ROOT / ".build" / ("dashboard-" + time.strftime("%Y%m%d%H%M%S"))
    context.mkdir(parents=True)
    for directory in ["src", "test", "public"]:
        if (source / directory).exists():
            shutil.copytree(source / directory, context / directory)
    for pattern in ["package*.json", "tsconfig*.json", "next-env.d.ts", "next.config.mjs",
                    "postcss.config.mjs", "tailwind.config.ts", "vitest.config.ts", ".eslintrc.json",
                    "Dockerfile", ".dockerignore"]:
        for path in source.glob(pattern):
            shutil.copy2(path, context / path.name)

    tag = f"{REGION}-docker.pkg.dev/{PROJECT}/landing-optimizer-v1/dashboard:{context.name}"
    config = {
        "steps": [{"name": "gcr.io/cloud-builders/docker", "args": [
            "build", "--build-arg", "API_URL=https://landing-optimizer-api-505424813528.southamerica-east1.run.app/v1",
            "-t", tag, "."]}],
        "images": [tag],
    }
    (context / "cloudbuild.json").write_text(json.dumps(config, indent=2) + "\n")
    build_id = cloud("builds", "submit", str(context), f"--config={context / 'cloudbuild.json'}",
                     "--async", "--format=value(id)", capture=True)
    print(f"Cloud Build: {build_id}", flush=True)
    while True:
        result = json.loads(cloud("builds", "describe", build_id, "--format=json", capture=True))
        if result["status"] == "SUCCESS":
            image = tag.split(":")[0] + "@" + result["results"]["images"][0]["digest"]
            break
        if result["status"] not in ["QUEUED", "WORKING", "PENDING"]:
            raise RuntimeError(f"Cloud Build {build_id}: {result['status']}")
        time.sleep(10)

    release_path = ROOT / "release.auto.tfvars.json"
    release = json.loads(release_path.read_text())
    release["dashboard_image"] = image
    release_path.write_text(json.dumps(release, indent=2) + "\n")
    apply()
    print("Dashboard deployed. Run the live login and session-refresh smoke checks.")


if __name__ == "__main__":
    main()
