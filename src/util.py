#!/usr/bin/env python3

from pathlib import Path
import subprocess as sp
import shutil


def install_python_dependencies(requirements_file: Path) -> None:
    # Specifically point at the system's Python, to install modules on the system level
    sp.run(['sudo', 'pip3', 'install', '-r', requirements_file], check=True)


def install_service_file(source_path: str, service_name: str) -> None:
    target_path = Path(f'/etc/systemd/system/{service_name.lower()}.service')
    shutil.copyfile(source_path, target_path)
    sp.run(['systemctl', 'daemon-reload'], check=False)


def start_service(service_name: str) -> None:
    sp.run(['systemctl', 'start', f'{service_name.lower()}.service'], check=False)


def stop_service(service_name: str) -> None:
    sp.run(['systemctl', 'stop', f'{service_name.lower()}.service'], check=False)


def service_running(service_name: str) -> bool:
    service_status = sp.run(['service', f'{service_name.lower()}', 'status'], stdout=sp.PIPE, check=False).returncode
    return service_status == 0
