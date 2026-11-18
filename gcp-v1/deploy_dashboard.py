"""Compatibility entry point; cloud operations live in personal-cloud-infrastructure."""
from pathlib import Path
import runpy
import sys

central = Path(__file__).resolve().parents[2] / "personal-cloud-infrastructure/solutions/landing-optimizer/terraform/v1"
if not (central / "deploy_dashboard.py").is_file():
    raise SystemExit("Use a workspace containing personal-cloud-infrastructure; see its docs/reconciliation.md")
sys.path.insert(0, str(central))
globals().update(runpy.run_path(str(central / "deploy_dashboard.py"), run_name="__main__" if __name__ == "__main__" else "central_deploy_dashboard"))
