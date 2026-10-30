"""Real Compose regression, opt-in and isolated from application databases."""

import os
import subprocess
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DOCKER_DEPLOY") != "1", reason="requires explicit local Docker opt-in"
)


@pytest.mark.parametrize("failure", ["migration", "build"])
def test_failed_release_preserves_running_api(tmp_path, failure):
    project = "nt-release-" + uuid.uuid4().hex[:12]
    image = project + ":runtime"
    (tmp_path / "Dockerfile").write_text("FROM redis:7-alpine\nRUN true\n")
    (tmp_path / ".env.vps").write_text("RELEASE=old\nMIGRATION_EXIT=0\n")
    (tmp_path / "docker-compose.vps.yml").write_text(
        f"""name: {project}
x-runtime: &runtime
  image: {image}
  build: .
  command: ["sleep", "3600"]
  environment:
    RELEASE: ${{RELEASE}}
  depends_on:
    migrate: {{condition: service_completed_successfully}}
services:
  postgres:
    image: redis:7-alpine
    command: ["sleep", "3600"]
  redis:
    image: redis:7-alpine
    command: ["sleep", "3600"]
  migrate:
    image: {image}
    command: ["sh", "-c", "exit $$MIGRATION_EXIT"]
    environment:
      MIGRATION_EXIT: ${{MIGRATION_EXIT}}
  api:
    <<: *runtime
  worker:
    <<: *runtime
  beat:
    <<: *runtime
"""
    )
    command = ["docker", "compose", "--env-file", ".env.vps", "-f", "docker-compose.vps.yml"]

    def run(args, *, check=True):
        return subprocess.run(
            args, cwd=tmp_path, text=True, capture_output=True, check=check, timeout=120
        )

    script = Path(
        os.getenv(
            "VPS_RELEASE_SCRIPT", str(Path(__file__).resolve().parents[2] / "deploy/vps-release.sh")
        )
    )
    try:
        run(command + ["build", "api"])
        run(command + ["up", "-d"])
        old = {
            name: run(command + ["ps", "-q", name]).stdout.strip()
            for name in ("api", "worker", "beat")
        }
        assert all(old.values())
        (tmp_path / ".env.vps").write_text("RELEASE=new\nMIGRATION_EXIT=1\n")
        if failure == "build":
            (tmp_path / "Dockerfile").write_text("FROM redis:7-alpine\nRUN exit 1\n")
        attempt = run(["sh", str(script), str(tmp_path)], check=False)
        assert attempt.returncode != 0
        for name, identity in old.items():
            assert run(command + ["ps", "-q", name]).stdout.strip() == identity
            assert (
                run(
                    ["docker", "inspect", "--format", "{{.State.Running}}", identity]
                ).stdout.strip()
                == "true"
            )
    finally:
        run(command + ["down", "--remove-orphans"], check=False)
        run(["docker", "image", "rm", image], check=False)
