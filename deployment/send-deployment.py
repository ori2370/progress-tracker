"""Send the deployment files to EC2 through AWS Systems Manager."""

import base64
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path


def aws(*arguments):
    """Run an AWS CLI command and return its JSON response."""
    result = subprocess.run(
        ["aws", "ssm", *arguments, "--output", "json"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    return json.loads(result.stdout)


def prepare_command(instance_id, image_uri):
    """Validate inputs and build the commands that run on EC2."""
    if not re.fullmatch(r"i-[0-9a-f]{17}", instance_id):
        raise ValueError("Enter a valid EC2 instance ID.")

    image_pattern = (
        r"[0-9]{12}\.dkr\.ecr\.us-east-1\.amazonaws\.com/"
        r"progress-tracker@sha256:[0-9a-f]{64}"
    )

    if not re.fullmatch(image_pattern, image_uri):
        raise ValueError("Enter a valid Progress Tracker ECR image digest.")

    directory = Path(__file__).resolve().parent

    commands = [
        "set -eu",
        "cloud-init status --wait",
        "install -d -m 0750 /opt/progress-tracker",
    ]

    for filename in ("compose.yml", "deploy.sh"):
        encoded = base64.b64encode(
            (directory / filename).read_bytes()
        ).decode("ascii")

        destination = f"/opt/progress-tracker/{filename}"

        commands.append(
            f"printf '%s' {shlex.quote(encoded)} "
            f"| base64 --decode > {shlex.quote(destination)}"
        )

    commands.extend([
        "chmod 0640 /opt/progress-tracker/compose.yml",
        "chmod 0750 /opt/progress-tracker/deploy.sh",
        "/bin/bash /opt/progress-tracker/deploy.sh "
        + shlex.quote(image_uri),
    ])

    return {
        "DocumentName": "AWS-RunShellScript",
        "InstanceIds": [instance_id],
        "Comment": "Deploy Progress Tracker from GitHub Actions",
        "Parameters": {
            "commands": ["\n".join(commands)],
            "executionTimeout": ["900"],
        },
    }


def wait_for_deployment(command_id, instance_id):
    """Wait for completion and print the remote command output."""
    deadline = time.monotonic() + 960
    previous_status = None

    while time.monotonic() < deadline:
        try:
            result = aws(
                "get-command-invocation",
                "--command-id", command_id,
                "--instance-id", instance_id,
            )
        except RuntimeError as error:
            if "InvocationDoesNotExist" not in str(error):
                raise

            time.sleep(5)
            continue

        status = result["Status"]

        if status != previous_status:
            print(f"Deployment status: {status}", flush=True)
            previous_status = status

        if status in {"Success", "Failed", "Cancelled", "TimedOut"}:
            print(result.get("StandardOutputContent", ""))
            print(result.get("StandardErrorContent", ""))

            if status != "Success":
                raise RuntimeError(f"Deployment ended with status: {status}")

            return

        time.sleep(5)

    raise TimeoutError(
        f"Stopped waiting for SSM command {command_id}. "
        "The remote command may still be running; inspect it in AWS."
    )


def main():
    instance_id = os.environ["INSTANCE_ID"]
    image_uri = os.environ["IMAGE_URI"]

    payload = prepare_command(instance_id, image_uri)

    response = aws(
        "send-command",
        "--cli-input-json", json.dumps(payload),
    )

    command_id = response["Command"]["CommandId"]
    print(f"SSM command ID: {command_id}", flush=True)

    wait_for_deployment(command_id, instance_id)


if __name__ == "__main__":
    main()