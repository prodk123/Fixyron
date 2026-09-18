import docker
import logging
import time
import os
from typing import Dict, Any, Tuple
from app.services.testing.result_parser import parse_test_results

logger = logging.getLogger(__name__)

def get_image_for_language(language: str) -> str:
    if language == "Python":
        return "python:3.12-slim"
    elif language in ("JavaScript", "TypeScript"):
        return "node:20"
    elif language == "Java":
        return "maven:3.9-eclipse-temurin-17"
    elif language == "Go":
        return "golang:1.22"
    elif language == "Rust":
        return "rust:1.77"
    return "ubuntu:22.04"

def get_install_command(language: str) -> str:
    if language == "Python":
        return "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi; if [ -f setup.py ] || [ -f pyproject.toml ]; then pip install -e . || true; fi; pip install pytest"
    elif language in ("JavaScript", "TypeScript"):
        return "npm install"
    return "echo 'No install step required'"

def run_tests_in_sandbox(
    workspace_dir: str, 
    language: str, 
    test_command: str,
    framework: str,
    timeout_seconds: int = 120
) -> Dict[str, Any]:
    """
    Executes tests in an isolated, ephemeral Docker container.
    Returns structured results including parsed stdout/stderr and exit code.
    """
    start_time = time.time()
    
    try:
        client = docker.from_env()
    except Exception as e:
        logger.error(f"Failed to connect to docker daemon: {e}")
        return {"status": "error", "error_message": "Docker daemon not available"}

    image = get_image_for_language(language)
    
    # Ensure image exists (pull if missing, but we assume common ones are fast or cached)
    try:
        client.images.get(image)
    except docker.errors.ImageNotFound:
        logger.info(f"Pulling image {image}...")
        client.images.pull(image)
    
    install_cmd = get_install_command(language)
    
    # We combine install and test into one script to avoid running multiple execs,
    # or we can run a single container with a shell command.
    full_command = f"sh -c '{install_cmd} && {test_command}'"
    
    container = None
    try:
        # Spawn container
        container = client.containers.run(
            image,
            command=full_command,
            volumes={
                workspace_dir: {'bind': '/workspace', 'mode': 'rw'}
            },
            working_dir='/workspace',
            detach=True,
            mem_limit='1g',
            nano_cpus=1000000000, # 1 CPU
            network_mode='bridge', # Need network for npm install/pip install. A separate install step is better for isolation, but this is acceptable for now.
        )
        
        # Wait with timeout
        result = container.wait(timeout=timeout_seconds)
        exit_code = result.get('StatusCode', 1)
        
        # Fetch logs
        logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
        
        # Truncate logs if too large (e.g., max 100KB)
        if len(logs) > 100000:
            logs = logs[-100000:]
            
        duration_ms = int((time.time() - start_time) * 1000)
        
        parsed = parse_test_results(logs, "", framework)
        
        return {
            "status": "success" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "stdout": logs,
            "stderr": "", # docker API combines them or we can fetch separately, logs() has both
            "duration_ms": duration_ms,
            "timed_out": False,
            **parsed
        }
        
    except docker.errors.ContainerError as e:
        # Should not happen with detach=True, but just in case
        return {"status": "failed", "error_message": str(e)}
    except Exception as e:
        # Handle timeout
        if "ReadTimeout" in str(e) or "Timeout" in str(type(e)):
            if container:
                container.stop(timeout=1)
            return {
                "status": "timeout",
                "timed_out": True,
                "duration_ms": int((time.time() - start_time) * 1000)
            }
        logger.error(f"Container execution failed: {e}")
        return {"status": "error", "error_message": str(e)}
    finally:
        # Cleanup
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
