# Main-branch deployment

The AI, API and dashboard repositories run their existing checks on pull requests
and pushes. A successful push to `main`, including a merged PR, calls
`RodrigoVanzelotti/landing-optimizer-infra/.github/workflows/deploy.yml@main`.
The CI workflow also supports manual retries with `workflow_dispatch` on `main`.

The reusable workflow checks out the triggering application commit and the
infrastructure repository, runs release safety tests, authenticates to Google
with Workload Identity Federation, builds/tests a container on the GitHub runner,
pushes it to Artifact Registry, and applies Terraform with that image's digest.
The API image includes the snippet from its current `main`; the image build tests
both packages. SDK-only changes are picked up on the next API deployment.

For API releases, the migration job is updated and executed successfully before
the API service is updated. Each service has a startup probe and the workflow
checks its public health/login endpoint after Terraform completes. A failed
build/test or migration stops deployment. There is no automatic database rollback.

## Credentials and concurrency

- No service-account key or personal GitHub token is stored in repository secrets.
- Google trusts only owner ID `85701210`, the three configured repository IDs,
  branch `refs/heads/main`, and `push`/`workflow_dispatch` events. PR jobs cannot
  obtain deployment credentials. Protect `main` and require CI before merging.
- `landing-optimizer-deployer` can read infrastructure metadata, administer Cloud
  Run, write this repository's container images and the V1 state bucket, and act
  as the three runtime identities. It has no Secret Manager payload access and
  cannot change project IAM, database instances or secret values.
- A GCS object at `landing-optimizer/v1/deployment.lock` serializes releases across
  all three repositories. GitHub's per-repository concurrency alone is insufficient.
- After acquiring the lock, the workflow reads the currently deployed images from
  Terraform state and changes only its component's image. This prevents one
  repository from rolling another service back. Superseded main commits are skipped.
- Failed runs release their lock in `finally`. A later run can recover a stale
  deployment lock only when GitHub confirms its owner finished or a new attempt
  superseded the recorded attempt. Unknown owners and API failures fail closed.
- A forcibly killed Terraform process can still leave a backend `.tflock`. Confirm
  that its workflow is stopped before manually unlocking it. Do not run the old
  local bootstrap/release scripts concurrently with automatic deployments.

The Google identity, permissions and AI foundation are declared in `cicd.tf`,
`ai.tf` and `main.tf`. Bootstrap or permission changes require the existing project
administrator; application releases do not get IAM-administration privileges.
The central personal-cloud-infrastructure YAML registration remains disabled to
avoid managing the same resources from a second state.

## AI V1

The AI service uses its existing deterministic `stub` provider. It accepts internal
requests only with the bearer token from `lo-v1-ai-token` version 1. The API gets
the same token through `AI_SERVICE_TOKEN`, and its `AI_SERVICE_URL` points at the
Google-generated AI URL. Cloud Run invocation is public so the existing bearer-token
protocol works; `/internal/*` remains application-authenticated. Changing to a paid
LLM requires explicitly configuring its provider and a separately managed key.

## Operations

Check the `CI` run in the application repository. Its deployment job records the
application commit, exact image digest and live endpoint in the Actions summary.
Infrastructure/provider versions and checksums are pinned in Terraform.

Normal deployment is **merge to main**. To retry a failed release, rerun the failed
workflow after fixing its cause, or dispatch `CI` on `main`. Do not deploy an older
commit over a newer `main`; the script deliberately skips superseded commits.

The legacy local scripts remain for administrator bootstrap/recovery. Their
ignored `release.auto.tfvars.json` can become stale after automatic releases;
refresh its image values from the live Terraform state before a full manual plan.
Never approve a plan that deletes/replaces persistent resources or rolls another
component's image back. The automatic script rejects all deletions/replacements.

Administrator bootstrap must enable IAM Credentials (`iamcredentials.googleapis.com`),
STS (`sts.googleapis.com`) and Cloud Resource Manager (`cloudresourcemanager.googleapis.com`)
in the deployment project, in addition to the V1 runtime APIs. This was completed
for `landing-optimizer-landing-page`. Secret values remain administrator-managed.

Verified 2026-11-10: all three application `CI` runs succeeded, their Cloud Run
last modifier is the deployment service account, and the final Terraform plan is
clean. AI run `42879925133`, API run `42879936463` (migration execution
`landing-optimizer-migrate-v1-b5x7p`), dashboard run `42880236062`. Live AI auth/scoring
and dashboard session/data checks passed. AI remains on the deterministic provider.
